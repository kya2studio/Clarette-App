/* Clarette license fulfillment webhook -- deploy this as a Cloudflare Worker.
 *
 * What it does: Gumroad (or any platform that can POST a webhook) notifies
 * this Worker when a sale happens; it signs a new license key with the
 * same Ed25519 scheme as license.py/generate_license.py, then emails it to
 * the buyer via Resend.
 *
 * This is NOT tested against a live Cloudflare/Resend account (no
 * credentials to test with) -- treat it as a solid starting point, not a
 * guarantee. Ed25519 support in the Workers runtime's WebCrypto is fairly
 * recent; if `crypto.subtle.importKey('raw', ...)` for Ed25519 errors on
 * your account's runtime version, that's the first thing to check.
 *
 * One-time setup (free tiers cover low volume):
 *   1. workers.cloudflare.com -> Create a Worker -> paste this file's code
 *      into the online editor (no CLI/build step needed) -> Deploy.
 *   2. In the Worker's Settings > Variables, add two encrypted secrets:
 *        LICENSE_PRIVATE_KEY  = the same value from your password manager
 *        RESEND_API_KEY       = an API key from resend.com (free tier)
 *   3. Gumroad: Settings > Advanced > "Ping" (webhook) URL = this Worker's
 *      URL. Other platforms: point their "order completed" webhook here
 *      and adjust `extractEmail()` below to match their payload shape.
 *   4. Change FROM_EMAIL below to an address/domain verified in Resend.
 */

const FROM_EMAIL = 'Clarette <hi@kleberdavila.com>'; // must be a Resend-verified sender

function b64urlEncode(bytes) {
  let s = btoa(String.fromCharCode(...new Uint8Array(bytes)));
  return s.replace(/\+/g, '-').replace(/\//g, '_');
}

async function signLicense(email, privateKeyB64) {
  const raw = Uint8Array.from(atob(privateKeyB64.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('raw', raw, { name: 'Ed25519' }, false, ['sign']);
  const payload = new TextEncoder().encode(JSON.stringify({
    email, issued: new Date().toISOString().slice(0, 10), type: 'purchased',
  }));
  const signature = await crypto.subtle.sign('Ed25519', key, payload);
  return `${b64urlEncode(payload)}.${b64urlEncode(signature)}`;
}

// Gumroad's ping webhook sends form-encoded fields; `email` is one of them.
// Adjust this for whichever platform you actually end up using.
async function extractEmail(request) {
  const form = await request.formData();
  const email = form.get('email');
  if (!email) throw new Error('No email field in webhook payload');
  return email;
}

async function sendLicenseEmail(email, license, resendApiKey) {
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${resendApiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: FROM_EMAIL,
      to: email,
      subject: 'Your Clarette license key',
      text: `Thanks for buying Clarette!\n\nYour license key:\n${license}\n\nOpen Clarette, paste this into the activation dialog (or Settings > License > "Use a Different Key"), and click Activate.`,
    }),
  });
  if (!r.ok) throw new Error('Resend API error: ' + await r.text());
}

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') return new Response('OK', { status: 200 });
    try {
      const email = await extractEmail(request);
      const license = await signLicense(email, env.LICENSE_PRIVATE_KEY);
      await sendLicenseEmail(email, license, env.RESEND_API_KEY);
      return new Response('OK', { status: 200 });
    } catch (e) {
      console.error(e);
      return new Response('Error: ' + e.message, { status: 500 });
    }
  },
};
