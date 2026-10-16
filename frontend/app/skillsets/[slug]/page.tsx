import { notFound } from "next/navigation";
import { getSettings, getSkillset } from "@/lib/api";
import { SkillsetDetail } from "@/components/skillset-detail";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export default async function SkillsetPage(props: PageProps) {
  const params = await props.params;
  const [skillset, siteSettings] = await Promise.all([getSkillset(params.slug, true), getSettings(true)]);
  if (!skillset) return notFound();
  return (
    <SkillsetDetail initial={skillset} accessInstructionsUrl={siteSettings.github_access_instructions_url} />
  );
}
