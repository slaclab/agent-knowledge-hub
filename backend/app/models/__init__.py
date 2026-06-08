from app.models.flag import SkillFlag
from app.models.install_event import SkillInstallEvent
from app.models.label import Label, SkillLabel
from app.models.rating import Rating
from app.models.revision import SkillRevision
from app.models.settings import SiteSettings
from app.models.skill import Skill

ALL_MODELS = [Skill, SkillRevision, Rating, Label, SkillLabel, SkillFlag, SiteSettings, SkillInstallEvent]
