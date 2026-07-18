import githubLogo from "../assets/sources/github/invertocat-black.svg";

const SOURCE_LOGOS: Record<string, string> = {
  github: githubLogo,
};

export function getSourceLogo(source: string): string | null {
  return SOURCE_LOGOS[source] ?? null;
}
