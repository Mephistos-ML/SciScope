import { getSourceLogo } from "../lib/sourceLogos";

type SourceBadgeProps = {
  source: string;
};

export function SourceBadge({ source }: SourceBadgeProps) {
  const logo = getSourceLogo(source);

  return (
    <span className="source-badge">
      {logo ? <img className="source-badge-logo" src={logo} alt="" aria-hidden="true" /> : null}
      <span>{source}</span>
    </span>
  );
}
