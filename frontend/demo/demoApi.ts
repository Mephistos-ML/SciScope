import type { Connect, Plugin } from "vite";

const viewer = {
  userId: "demo_user",
  email: "demo@sciscope.local",
  displayName: "Ernest Borysenko",
  avatarUrl: null,
  features: [],
};

const subscriptions = [
  {
    subscriptionId: "sub_demo_paranmr",
    repository: {
      repositoryId: "github:repo:paranmr",
      source: "github",
      fullName: "Mephistos-ML/paranmr",
      url: "https://github.com/Mephistos-ML/paranmr",
    },
    selectedQuery: "paramagnetic NMR analysis",
    createdAt: "2026-08-12T09:20:00Z",
  },
  {
    subscriptionId: "sub_demo_openfold",
    repository: {
      repositoryId: "github:repo:openfold",
      source: "github",
      fullName: "aqlaboratory/openfold",
      url: "https://github.com/aqlaboratory/openfold",
    },
    selectedQuery: "protein structure prediction",
    createdAt: "2026-08-03T14:45:00Z",
  },
  {
    subscriptionId: "sub_demo_mdanalysis",
    repository: {
      repositoryId: "github:repo:mdanalysis",
      source: "github",
      fullName: "MDAnalysis/mdanalysis",
      url: "https://github.com/MDAnalysis/mdanalysis",
    },
    selectedQuery: "molecular dynamics trajectory analysis",
    createdAt: "2026-07-28T11:10:00Z",
  },
  {
    subscriptionId: "sub_demo_gromacs",
    repository: {
      repositoryId: "gitlab:repo:gromacs",
      source: "gitlab",
      fullName: "gromacs/gromacs",
      url: "https://gitlab.com/gromacs/gromacs",
    },
    selectedQuery: "molecular simulation software",
    createdAt: "2026-07-21T08:30:00Z",
  },
];

const feedItems = [
  feedEvent({
    id: "event_demo_paranmr_release",
    subscriptionId: "sub_demo_paranmr",
    repositoryId: "github:repo:paranmr",
    repositoryFullName: "Mephistos-ML/paranmr",
    repositorySource: "github",
    repositoryUrl: "https://github.com/Mephistos-ML/paranmr",
    selectedQuery: "paramagnetic NMR analysis",
    title: "v1.8.0 — improved susceptibility fitting",
    summary: "New constrained fitting workflow and clearer uncertainty reporting for PCS analysis.",
    source: "github",
    signalKind: "release",
    url: "https://github.com/Mephistos-ML/paranmr/releases",
    publishedAt: "2026-09-08T14:30:00Z",
  }),
  feedEvent({
    id: "event_demo_openfold_commit",
    subscriptionId: "sub_demo_openfold",
    repositoryId: "github:repo:openfold",
    repositoryFullName: "aqlaboratory/openfold",
    repositorySource: "github",
    repositoryUrl: "https://github.com/aqlaboratory/openfold",
    selectedQuery: "protein structure prediction",
    title: "Improve template feature validation",
    summary: "Default-branch commit updating validation around template-derived model inputs.",
    source: "github",
    signalKind: "commit",
    url: "https://github.com/aqlaboratory/openfold/commits/main",
    publishedAt: "2026-09-08T09:12:00Z",
  }),
  feedEvent({
    id: "event_demo_mdanalysis_release",
    subscriptionId: "sub_demo_mdanalysis",
    repositoryId: "github:repo:mdanalysis",
    repositoryFullName: "MDAnalysis/mdanalysis",
    repositorySource: "github",
    repositoryUrl: "https://github.com/MDAnalysis/mdanalysis",
    selectedQuery: "molecular dynamics trajectory analysis",
    title: "Release 2.9.0",
    summary: "New analysis conveniences and compatibility updates for molecular-dynamics workflows.",
    source: "github",
    signalKind: "release",
    url: "https://github.com/MDAnalysis/mdanalysis/releases",
    publishedAt: "2026-09-07T16:40:00Z",
  }),
  feedEvent({
    id: "event_demo_gromacs_commit",
    subscriptionId: "sub_demo_gromacs",
    repositoryId: "gitlab:repo:gromacs",
    repositoryFullName: "gromacs/gromacs",
    repositorySource: "gitlab",
    repositoryUrl: "https://gitlab.com/gromacs/gromacs",
    selectedQuery: "molecular simulation software",
    title: "Refine PME communication scheduling",
    summary: "Default-branch performance work for parallel particle-mesh Ewald calculations.",
    source: "gitlab",
    signalKind: "commit",
    url: "https://gitlab.com/gromacs/gromacs/-/commits/main",
    publishedAt: "2026-09-07T10:05:00Z",
  }),
  feedEvent({
    id: "event_demo_paranmr_commit",
    subscriptionId: "sub_demo_paranmr",
    repositoryId: "github:repo:paranmr",
    repositoryFullName: "Mephistos-ML/paranmr",
    repositorySource: "github",
    repositoryUrl: "https://github.com/Mephistos-ML/paranmr",
    selectedQuery: "paramagnetic NMR analysis",
    title: "Document anisotropic tensor constraints",
    summary: "Default-branch documentation and examples for constrained tensor fitting.",
    source: "github",
    signalKind: "commit",
    url: "https://github.com/Mephistos-ML/paranmr/commits/main",
    publishedAt: "2026-09-06T12:15:00Z",
  }),
];

export function demoApiPlugin(): Plugin {
  return {
    name: "sciscope-demo-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(((request, response, next) => {
        const demoRequest = request as unknown as { method?: string; url?: string };
        const path = demoRequest.url?.split("?")[0];
        const body = resolveDemoResponse(demoRequest.method ?? "GET", path);
        if (body === undefined) {
          next();
          return;
        }

        response.statusCode = 200;
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify(body));
      }) as Connect.NextHandleFunction);
    },
  };
}

function resolveDemoResponse(method: string, path: string | undefined): object | undefined {
  if (method === "GET" && path === "/api/me") return { user: viewer };
  if (method === "GET" && path === "/api/subscriptions") return { items: subscriptions };
  if (method === "GET" && path === "/api/feed") {
    return {
      items: feedItems,
      unreadCount: feedItems.filter((item) => item.readAt === null).length,
    };
  }
  if (method === "POST" && path === "/api/feed/read-all") {
    const updatedCount = feedItems.filter((item) => item.readAt === null).length;
    const readAt = new Date().toISOString();
    feedItems.forEach((item) => {
      item.readAt = readAt;
    });
    return { updatedCount };
  }
  if (method === "PATCH" && path?.indexOf("/api/feed/") === 0) {
    const eventId = path.slice("/api/feed/".length);
    let event: (typeof feedItems)[number] | undefined;
    for (const item of feedItems) {
      if (item.eventId === eventId) {
        event = item;
        break;
      }
    }
    if (!event) return undefined;
    event.readAt = new Date().toISOString();
    return { ...event, rawText: event.summary, normalizedText: event.summary, metadata: {} };
  }
  if (method === "POST" && path === "/api/logout") return { user: null };
  if (method === "DELETE" && path?.indexOf("/api/subscriptions/") === 0) {
    return { deleted: true };
  }
  return undefined;
}

function feedEvent(event: {
  id: string;
  subscriptionId: string;
  repositoryId: string;
  repositoryFullName: string;
  repositorySource: string;
  repositoryUrl: string;
  selectedQuery: string;
  title: string;
  summary: string;
  source: string;
  signalKind: string;
  url: string;
  publishedAt: string;
}) {
  return {
    eventId: event.id,
    subscriptionId: event.subscriptionId,
    repositoryId: event.repositoryId,
    repositoryFullName: event.repositoryFullName,
    repositorySource: event.repositorySource,
    repositoryUrl: event.repositoryUrl,
    selectedQuery: event.selectedQuery,
    title: event.title,
    summary: event.summary,
    source: event.source,
    signalKind: event.signalKind,
    url: event.url,
    publishedAt: event.publishedAt,
    createdAt: event.publishedAt,
    readAt: null as string | null,
  };
}
