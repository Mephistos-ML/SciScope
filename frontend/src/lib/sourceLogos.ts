import githubLogo from "../assets/sources/github/invertocat-black.svg";
import gitlabLogo from "../assets/sources/gitlab/gitlab-logo-600-rgb.svg";

const SOURCE_LOGOS: Record<string, string> = {
  github: githubLogo,
  gitlab: gitlabLogo,
};

export function getSourceLogo(source: string): string | null {
  return SOURCE_LOGOS[source] ?? null;
}
