---
name: vs-extension-oauth
description: 'Add OAuth 2.0 or OpenID Connect sign-in to a Visual Studio extension as a public client: gather provider inputs only when authentication is in scope, use MSAL.NET with silent-first acquisition, the WAM broker and a parent window for Microsoft Entra ID, authorization code with PKCE for other providers, a persistent encrypted token cache, and no client secret. Use when an extension signs users in or calls a protected API.'
---

# OAuth Sign-in for Visual Studio Extensions

Rules for authenticating users from an extension. An extension is installed on user machines, so it is always a public client.

## When not to use

- The extension does not sign users in or call a protected API. Do not ask for OAuth inputs in that case.

## Rules

### 1. Gather provider inputs only when authentication is in scope

- **Rule:** When a task adds or changes sign-in, confirm before writing code: the provider, the client (application) ID, the tenant model or authority, the scopes, the redirect URI strategy, and whether service-side components are needed. Do not guess any of them. Use placeholders in documentation.
- **Check:** The design lists each input with its source; documentation contains no real tenant ID, client ID, or endpoint.
- **Why:** A wrong authority or redirect URI fails only at sign-in time, often on another user's machine.

### 2. Never ship a client secret

- **Rule:** Do not put a client secret, certificate, or other confidential credential in the extension, its settings, or its VSIX. If the scenario needs one, move that part to a service.
- **Check:** A search of the source and the packaged VSIX finds no secret-like configuration value.
- **Why:** Anything in the extension can be extracted by any user.

### 3. Use MSAL.NET for Microsoft identity, silent first

- **Rule:** Build a `PublicClientApplication` and use the default redirect URI unless there is a documented reason to override it. Call `AcquireTokenSilent` first and call `AcquireTokenInteractive` only when silent acquisition requires user interaction.
- **Check:** The token service calls the silent path first and falls back to interactive only for `MsalUiRequiredException`.
- **Why:** This is the recommended pattern for desktop apps that call web APIs (Microsoft Learn).

### 4. Prefer the WAM broker for Microsoft Entra ID, and supply a parent window

- **Rule:** On Windows, enable the broker (`WithBroker`) for Microsoft Entra ID and register the broker redirect URI in the app registration. Supply a parent window handle with `WithParentActivityOrWindow`; in an out-of-process extension, design how that handle is obtained from Visual Studio and which thread shows the prompt, and fall back to the system browser when no handle is available.
- **Check:** The interactive prompt appears in front of Visual Studio, not behind it.
- **Why:** WAM is the recommended broker and requires a parent window; it supports only Microsoft Entra ID (Microsoft Learn).

### 5. Use authorization code with PKCE for other providers

- **Rule:** For providers other than Microsoft Entra ID, use the authorization code flow with PKCE in the system browser with a loopback or custom-scheme redirect. Do not embed a password form.
- **Check:** The authorization request includes a `code_challenge`, and the code exchange sends the matching verifier.
- **Why:** PKCE protects public clients that cannot keep a secret.

### 6. Persist the token cache securely

- **Rule:** If sign-in must survive a Visual Studio restart, persist the token cache with platform encryption (for example the MSAL cache extensions with DPAPI on Windows). Keep token acquisition, the cache, and API clients in separate components. Never log tokens.
- **Check:** Restarting Visual Studio reuses the cached account without a prompt, and logs contain no token values.
- **Why:** Without a persistent cache, users are prompted after every restart; MSAL also keeps account metadata there (Microsoft Learn).

### 7. Document the app registration

- **Rule:** Document the required app registration settings: platform type, redirect URIs, supported account types, and API permissions, using placeholders for identifiers.
- **Check:** A new developer can register the app from the documentation alone.
- **Why:** Missing registration settings produce sign-in errors that the extension cannot explain.
