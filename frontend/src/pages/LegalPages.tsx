import type { ReactNode } from "react";

export function PrivacyPage() {
  return <LegalPage title="Privacy Policy" updated="9 September 2026">
    <p>SciScope is operated by Ernest Borysenko ("SciScope", "we", "us"). Contact us at <a href="mailto:contact@sciscope.uk">contact@sciscope.uk</a>.</p>
    <h2>What we collect</h2><p>When you use Google Sign-In, we receive and store your Google subject identifier, verified email address, display name and, where provided, profile image. We also store subscriptions, Feed events and read state, search and repository-selection data, and security and rate-limit records such as hashed IP addresses and hashed search topics.</p>
    <h2>Why we use it</h2><p>We use this information to provide your account, save and monitor repositories, deliver your Feed, prevent abuse, secure the service and improve reliability. Our lawful bases are performance of our agreement with you and our legitimate interests in operating a secure, useful service.</p>
    <h2>Google and other providers</h2><p>Google data is used only to authenticate your SciScope account. We do not access your Gmail, Drive, GitHub or GitLab accounts. SciScope reads public repository information from GitHub and GitLab. When AI-assisted search planning or semantic retrieval is enabled, your search text may be sent to OpenAI to provide that feature.</p>
    <h2>Sharing and hosting</h2><p>We use service providers to run SciScope, including Vercel for the web application, Fly.io for the API and infrastructure providers for database hosting. We may use Google, GitHub, GitLab, OpenAI and Cloudflare Turnstile where the relevant feature is enabled. They process data only as needed to provide their services. We do not sell personal data or use it for advertising.</p>
    <h2>Cookies</h2><p>SciScope uses essential, secure HTTP-only cookies for your signed-in session (up to 30 days) and short-lived OAuth state and nonce cookies (up to 10 minutes). We do not use advertising cookies.</p>
    <h2>Retention and deletion</h2><p>We keep account data while your account is active. You can permanently delete your account in Account settings; this removes your profile, Google identity, sessions, subscriptions, personal Feed events and user search history from the active database. Global public repository data is retained because it is not personal account data. Backup copies may persist until their normal rotation cycle.</p>
    <h2>Your rights</h2><p>Depending on applicable law, you may request access, correction, deletion, restriction, portability or object to processing. Contact us at the address above. You may also complain to the UK Information Commissioner’s Office.</p>
    <h2>Changes</h2><p>We will update this policy when our practices change and revise the date above.</p>
  </LegalPage>;
}

export function TermsPage() {
  return <LegalPage title="Terms of Service and Acceptable Use" updated="9 September 2026">
    <p>These Terms govern your use of SciScope. By using the service, you agree to them.</p>
    <h2>The service</h2><p>SciScope helps users discover public scientific software repositories and monitor public releases and default-branch commits. Signals may be delayed, incomplete, unavailable or inaccurate. Do not rely on SciScope as the sole source for safety-critical, legal, financial, clinical or research decisions.</p>
    <h2>Your account</h2><p>You are responsible for activity under your account and for keeping access to your Google account secure. You may delete your SciScope account at any time through Account settings.</p>
    <h2>Acceptable use</h2><p>You must not interfere with the service, circumvent rate limits or security controls, scrape or automate it beyond normal use, probe for vulnerabilities without permission, upload unlawful material, impersonate others, or use SciScope to violate third-party rights or provider terms.</p>
    <h2>Repository information</h2><p>Repository content and metadata remain subject to their owners’ and providers’ terms. SciScope does not claim ownership of public repository information and does not guarantee its availability or accuracy.</p>
    <h2>Availability and liability</h2><p>SciScope is provided "as is" and "as available". To the extent permitted by law, we exclude warranties and are not liable for indirect or consequential loss. Nothing excludes liability that cannot lawfully be excluded.</p>
    <h2>Changes and termination</h2><p>We may change, suspend or discontinue the service, or restrict access where reasonably necessary for security, legal compliance or service operation. Continued use after updated Terms take effect means you accept them.</p>
    <h2>Governing law</h2><p>These Terms are governed by the laws of England and Wales. The courts of England and Wales have exclusive jurisdiction, except where mandatory consumer law provides otherwise.</p>
    <h2>Contact</h2><p>Questions about these Terms: <a href="mailto:contact@sciscope.uk">contact@sciscope.uk</a>.</p>
  </LegalPage>;
}

function LegalPage({ children, title, updated }: { children: ReactNode; title: string; updated: string }) {
  return <article className="legal-page"><p className="section-kicker">SciScope legal</p><h1 className="page-title">{title}</h1><p className="legal-updated">Last updated: {updated}</p>{children}</article>;
}
