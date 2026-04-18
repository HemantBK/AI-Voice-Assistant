/**
 * Voice cloning consent gate (Phase D'). Modal-blocking; must be ACKed
 * before the user can enroll or use a cloned voice. Consent storage lives
 * in src/services/consent.js (hasConsent / grantConsent / clearConsent).
 *
 * This component is a primitive. Real production use needs:
 *  - A recorded audio proof-of-consent.
 *  - Jurisdiction-aware copy (EU AI Act, US state-specific deepfake laws).
 *  - An admin-visible audit trail.
 */
import { useState } from "react";
import { grantConsent } from "../services/consent";

export default function ConsentGate({ onGrant, onDeny }) {
  const [checked, setChecked] = useState(false);

  const handleGrant = () => {
    grantConsent();
    onGrant?.();
  };

  return (
    <div className="consent-gate" role="dialog" aria-modal="true">
      <h2>Voice cloning — consent required</h2>
      <ol>
        <li>
          You will only clone voices from someone who has given you explicit,
          informed, and revocable permission. You will not clone public
          figures, minors without guardian consent, or anyone deceased.
        </li>
        <li>
          You will not use a cloned voice to deceive, defraud, or harass any
          person. You will not use it for non-consensual political, sexual,
          or financial content.
        </li>
        <li>
          Generated audio may be watermarked and can be identified as
          synthetic by downstream tools.
        </li>
        <li>
          This project's authors disclaim liability for misuse. Applicable
          laws (including deepfake statutes) still apply to you.
        </li>
      </ol>
      <label>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => setChecked(e.target.checked)}
        />{" "}
        I have read and agree to these terms.
      </label>
      <div className="consent-actions">
        <button onClick={onDeny}>Cancel</button>
        <button disabled={!checked} onClick={handleGrant}>Continue</button>
      </div>
    </div>
  );
}
