import { useState } from "react";

import type { Viewer } from "../types/api";

type AccountPageProps = {
  deleting: boolean;
  onDelete: () => void;
  onSignOut: () => void;
  viewer: Viewer;
};

export function AccountPage({ deleting, onDelete, onSignOut, viewer }: AccountPageProps) {
  const [confirmingDeletion, setConfirmingDeletion] = useState(false);
  const [confirmation, setConfirmation] = useState("");

  return (
    <section className="account-page">
      <p className="section-kicker">Account</p>
      <h1 className="page-title">Account settings</h1>
      <p className="page-intro">Manage your SciScope identity and account data.</p>
      <section className="account-panel">
        <p className="section-kicker">Profile</p>
        <div className="account-identity">
          {viewer.avatarUrl ? <img alt="" className="account-avatar" src={viewer.avatarUrl} /> : <span className="account-avatar account-avatar-fallback">{viewer.displayName.slice(0, 1)}</span>}
          <div><h2>{viewer.displayName}</h2><p>{viewer.email}</p><span>Managed through Google</span></div>
        </div>
      </section>
      <section className="account-panel">
        <p className="section-kicker">Session</p>
        <h2>Signed in with Google</h2>
        <p>Google is used only to identify your SciScope account.</p>
        <button className="outline-button" onClick={onSignOut} type="button">Sign out</button>
      </section>
      <section className="account-panel account-danger-zone">
        <p className="section-kicker">Danger zone</p>
        <h2>Delete account</h2>
        <p>This permanently deletes your profile, Google identity, sessions, subscriptions, Feed events, and user search history.</p>
        {!confirmingDeletion ? <button className="danger-button" onClick={() => setConfirmingDeletion(true)} type="button">Delete account</button> : <div className="account-delete-confirmation"><label htmlFor="delete-account-confirmation">Type DELETE to confirm</label><input id="delete-account-confirmation" onChange={(event) => setConfirmation(event.target.value)} value={confirmation} /><button className="danger-button" disabled={confirmation !== "DELETE" || deleting} onClick={onDelete} type="button">{deleting ? "Deleting..." : "Permanently delete account"}</button></div>}
      </section>
    </section>
  );
}
