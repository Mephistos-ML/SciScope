import { SiteChrome } from "../components/SiteChrome";
import { usePathname } from "../lib/router";
import { AboutPage } from "../pages/AboutPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LandingPage } from "../pages/LandingPage";
import { SourcesPage } from "../pages/SourcesPage";

export function App() {
  const { pathname, navigate } = usePathname();

  return (
    <SiteChrome currentPath={pathname} navigate={navigate}>
      {renderRoute(pathname, navigate)}
    </SiteChrome>
  );
}

function renderRoute(pathname: string, navigate: (href: string) => void) {
  if (pathname === "/") {
    return <LandingPage navigate={navigate} />;
  }

  if (pathname === "/dashboard") {
    return <DashboardPage navigate={navigate} />;
  }

  if (pathname === "/sources") {
    return <SourcesPage />;
  }

  if (pathname === "/about") {
    return <AboutPage />;
  }

  return <LandingPage navigate={navigate} />;
}
