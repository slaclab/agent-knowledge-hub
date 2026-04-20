import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface SupersededNoticeProps {
  slug: string;
  name?: string;
}

export function SupersededNotice({ slug, name }: SupersededNoticeProps) {
  return (
    <div className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 flex items-center gap-2 text-sm text-yellow-800">
      <ArrowRight className="h-4 w-4 flex-shrink-0" />
      <span>
        This skill has been superseded by{" "}
        <Link href={`/skills/${slug}`} className="font-semibold underline">
          {name ?? slug}
        </Link>
        .
      </span>
    </div>
  );
}
