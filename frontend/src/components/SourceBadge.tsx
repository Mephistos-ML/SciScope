import { getSourceLogo } from "../lib/sourceLogos";

type SourceBadgeProps = {
  href?: string;
  source: string;
};

export function SourceBadge({ href, source }: SourceBadgeProps) {
  const logo = getSourceLogo(source);
  const content = (
    <>
      {logo ? <img className="source-badge-logo" src={logo} alt="" aria-hidden="true" /> : null}
      <span>{source}</span>
    </>
  );

  if (href) {
    return (
      <a
        className="source-badge"
        href={href}
        rel="noreferrer noopener"
        target="_blank"
      >
        {content}
      </a>
    );
  }

  return <span className="source-badge">{content}</span>;
}
