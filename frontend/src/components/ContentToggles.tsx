import { Image, Film, Clock } from "lucide-react";

export interface ContentSelection {
  include_posts: boolean;
  include_reels: boolean;
  include_stories: boolean;
}

const OPTIONS: {
  key: keyof ContentSelection;
  label: string;
  icon: typeof Image;
}[] = [
  { key: "include_posts", label: "Posts", icon: Image },
  { key: "include_reels", label: "Reels", icon: Film },
  { key: "include_stories", label: "Stories", icon: Clock },
];

export default function ContentToggles({
  value,
  onChange,
}: {
  value: ContentSelection;
  onChange: (next: ContentSelection) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {OPTIONS.map(({ key, label, icon: Icon }) => {
        const on = value[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange({ ...value, [key]: !on })}
            className={on ? "chip-on" : "chip-off"}
          >
            <span className="flex items-center gap-1.5">
              <Icon className="h-3.5 w-3.5" />
              {label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
