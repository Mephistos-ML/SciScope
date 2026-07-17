import { useEffect, useState } from "react";

export function usePathname() {
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const handlePopState = () => {
      setPathname(window.location.pathname);
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  function navigate(nextPathname: string) {
    if (nextPathname === window.location.pathname) {
      return;
    }

    window.history.pushState({}, "", nextPathname);
    setPathname(nextPathname);
  }

  return { pathname, navigate };
}

type LinkProps = {
  children: React.ReactNode;
  className?: string;
  href: string;
  onNavigate: (href: string) => void;
};

export function AppLink({ children, className, href, onNavigate }: LinkProps) {
  return (
    <a
      className={className}
      href={href}
      onClick={(event) => {
        event.preventDefault();
        onNavigate(href);
      }}
    >
      {children}
    </a>
  );
}
