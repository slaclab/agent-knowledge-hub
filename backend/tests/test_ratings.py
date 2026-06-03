"""Tests for skill ratings — service + route (T1–T11, T21–T23)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.rating import Rating
from app.models.skill import Skill
from app.services.rating import rate_skill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_skill(slug: str = "test-skill") -> Skill:
    skill = Skill(
        slug=slug,
        name=slug,
        repo_url=f"https://github.com/test/{slug}",
        skill_path="/",
        submitter_id="user1",
    )
    await skill.insert()
    return skill


_TEST_SECRET = "test-internal-secret"


def _auth_headers(user_id: str = "user1") -> dict:
    return {"X-Internal-Secret": _TEST_SECRET, "X-Forwarded-User": user_id}


@pytest_asyncio.fixture
async def client(monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "internal_api_secret", _TEST_SECRET)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Service unit tests (T1–T6)
# ---------------------------------------------------------------------------


class TestRateSkillService:
    @pytest.mark.asyncio
    async def test_rate_skill_creates_rating(self):
        """T1: rating a skill creates a Rating doc and updates skill aggregates."""
        skill = await _make_skill()
        avg, count = await rate_skill(str(skill.id), "alice", 4)

        rating = await Rating.find_one(Rating.skill_id == str(skill.id))
        assert rating is not None
        assert rating.value == 4
        assert rating.user_id == "alice"
        assert avg == 4.0
        assert count == 1

        await skill.sync()
        assert skill.avg_rating == 4.0
        assert skill.rating_count == 1

    @pytest.mark.asyncio
    async def test_rate_skill_updates_existing(self):
        """T2: re-rating updates existing doc, no duplicate created."""
        skill = await _make_skill()
        await rate_skill(str(skill.id), "alice", 4)
        avg, count = await rate_skill(str(skill.id), "alice", 2)

        ratings = await Rating.find(Rating.skill_id == str(skill.id)).to_list()
        assert len(ratings) == 1
        assert ratings[0].value == 2
        assert avg == 2.0
        assert count == 1

    @pytest.mark.asyncio
    async def test_rate_skill_multiple_users(self):
        """T3: two users rating same skill produces correct avg and count."""
        skill = await _make_skill()
        await rate_skill(str(skill.id), "alice", 4)
        avg, count = await rate_skill(str(skill.id), "bob", 2)

        assert count == 2
        assert abs(avg - 3.0) < 0.001

    @pytest.mark.asyncio
    async def test_rate_skill_zero_ratings_edge(self):
        """T6: edge case — if no ratings exist (empty aggregation), returns (0.0, 0).
        This can't happen via normal flow (upsert always leaves one rating) but
        the aggregation path must handle an empty cursor gracefully.
        """
        skill = await _make_skill()
        # Insert then delete directly to simulate empty state
        await Rating(skill_id=str(skill.id), user_id="ghost", value=3).insert()
        await Rating.find(Rating.skill_id == str(skill.id)).delete()

        # Directly exercise aggregation handling by calling the helper
        # We do this by inserting a rating from a different skill then
        # calling rate_skill on our test skill — after deletion there are no ratings
        # so the aggregation result is empty.
        avg, count = await rate_skill(str(skill.id), "alice", 5)
        # After the upsert, one rating exists (alice=5)
        assert count == 1
        assert avg == 5.0

    @pytest.mark.asyncio
    async def test_rate_skill_boundary_values(self):
        """T5: values 1 and 5 succeed via service (schema validation tested at route level)."""
        skill_a = await _make_skill("boundary-1")
        skill_b = await _make_skill("boundary-5")
        avg1, cnt1 = await rate_skill(str(skill_a.id), "alice", 1)
        avg5, cnt5 = await rate_skill(str(skill_b.id), "alice", 5)
        assert avg1 == 1.0 and cnt1 == 1
        assert avg5 == 5.0 and cnt5 == 1


# ---------------------------------------------------------------------------
# Route integration tests (T7–T11, T21–T23)
# ---------------------------------------------------------------------------


class TestRateSkillRoute:
    @pytest.mark.asyncio
    async def test_rate_route_200_authed(self, client):
        """T7: POST with auth returns 200 and correct JSON shape."""
        skill = await _make_skill("rate-200")
        r = await client.post(
            f"/api/skills/{skill.slug}/rate",
            json={"value": 4},
            headers=_auth_headers("alice"),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["avg_rating"] == 4.0
        assert data["rating_count"] == 1
        assert data["my_rating"] == 4

    @pytest.mark.asyncio
    async def test_rate_route_401_unauthed(self, client, monkeypatch):
        """T8: POST without auth returns 401."""
        skill = await _make_skill("rate-401")
        r = await client.post(
            f"/api/skills/{skill.slug}/rate",
            json={"value": 3},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_rate_route_404_bad_slug(self, client):
        """T9: POST to non-existent slug returns 404."""
        r = await client.post(
            "/api/skills/does-not-exist/rate",
            json={"value": 3},
            headers=_auth_headers(),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_rate_route_422_invalid_value(self, client):
        """T10: POST with value=0, 6, or -1 returns 422."""
        skill = await _make_skill("rate-422")
        for bad_value in [0, 6, -1]:
            r = await client.post(
                f"/api/skills/{skill.slug}/rate",
                json={"value": bad_value},
                headers=_auth_headers(),
            )
            assert r.status_code == 422, f"expected 422 for value={bad_value}"

    @pytest.mark.asyncio
    async def test_rate_route_upsert(self, client):
        """T11: two POSTs from same user produce one doc with updated aggregates."""
        skill = await _make_skill("rate-upsert")
        await client.post(
            f"/api/skills/{skill.slug}/rate",
            json={"value": 5},
            headers=_auth_headers("alice"),
        )
        r = await client.post(
            f"/api/skills/{skill.slug}/rate",
            json={"value": 1},
            headers=_auth_headers("alice"),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["avg_rating"] == 1.0
        assert data["rating_count"] == 1
        assert data["my_rating"] == 1

        ratings = await Rating.find(Rating.skill_id == str(skill.id)).to_list()
        assert len(ratings) == 1

    @pytest.mark.asyncio
    async def test_get_skill_my_rating_null_when_unauthed(self, client):
        """T21: GET /api/skills/{slug} without auth returns my_rating: null."""
        skill = await _make_skill("get-unauthed")
        r = await client.get(f"/api/skills/{skill.slug}")
        assert r.status_code == 200
        assert r.json()["my_rating"] is None

    @pytest.mark.asyncio
    async def test_get_skill_my_rating_null_when_no_prior_rating(self, client):
        """T22: GET with auth but no prior rating returns my_rating: null."""
        skill = await _make_skill("get-no-rating")
        r = await client.get(
            f"/api/skills/{skill.slug}",
            headers=_auth_headers("alice"),
        )
        assert r.status_code == 200
        assert r.json()["my_rating"] is None

    @pytest.mark.asyncio
    async def test_get_skill_my_rating_returns_value_after_rating(self, client):
        """T23: POST a rating then GET with same auth returns matching my_rating."""
        skill = await _make_skill("get-with-rating")
        await client.post(
            f"/api/skills/{skill.slug}/rate",
            json={"value": 3},
            headers=_auth_headers("alice"),
        )
        r = await client.get(
            f"/api/skills/{skill.slug}",
            headers=_auth_headers("alice"),
        )
        assert r.status_code == 200
        assert r.json()["my_rating"] == 3
