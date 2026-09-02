# Levolia Desktop

Fork de [hermes-agent](https://github.com/NousResearch/hermes-agent) (licence MIT, Nous Research).
Seule l'application desktop (`apps/desktop`) est rebrandée. L'agent Python reste
Hermes et tourne sur un VPS par client. L'app installée sur le poste du client ne
fait que se connecter à ce serveur.

Branche de travail : `levolia`. La branche `main` reste alignée sur l'amont pour
faciliter les fusions.

## Ce qui a été modifié

- `apps/desktop/package.json` : nom produit, identifiant `ai.levolia.desktop`,
  nom des installeurs, textes macOS, schéma de lien profond `levolia://`.
- `apps/desktop/electron/main.ts` : schéma de lien profond aligné (`levolia`, `levolia-dev`).
- `apps/desktop/src/components/desktop-install-overlay.tsx` : le premier lancement
  affiche directement le formulaire de connexion distante. L'option
  « installer en local » n'est plus proposée.
- `apps/desktop/src/components/first-run-remote-form.tsx` : bouton Retour masquable.
- `apps/desktop/src/components/brand-mark.tsx` : logo remplacé par un marqueur
  Levolia provisoire (à remplacer par le vrai logo).
- `apps/desktop/src/i18n/{en,ar,ja}.ts` : « Hermes » remplacé par « Levolia » dans
  les textes visibles, textes d'onboarding réécrits (adresse du serveur, jeton d'accès).
  Les mentions du service « Nous Cloud » sont conservées telles quelles.
- `apps/desktop/index.html` : titre de fenêtre.

## Construire l'app

Depuis la racine du dépôt, une seule fois :

```bash
npm install
```

Puis dans `apps/desktop` :

```bash
npm run dev            # développement (Vite + Electron)
npm run dist:mac       # DMG + zip
npm run dist:win       # NSIS + MSI (à lancer sur Windows)
```

Vérifications :

```bash
npm run typecheck
npm run test:ui
```

## Provisionner un VPS client

1. Installer Hermes sur le VPS (script `setup-hermes.sh` ou Docker, voir le README amont).
2. Configurer le fournisseur de modèle et les clés API dans la config Hermes du VPS.
3. Définir le jeton d'accès et l'URL publique, par exemple dans le `.env` de Hermes :

   ```bash
   HERMES_DASHBOARD_SESSION_TOKEN=<jeton long généré, ex: openssl rand -base64 32>
   ```

   et dans la config Hermes, `dashboard.public_url` = `https://<client>.levolia.ai`.
   Sans jeton fixé, Hermes en génère un aléatoire à chaque démarrage.
4. Lancer le dashboard en écoute locale et le publier derrière un reverse proxy TLS :

   ```bash
   hermes dashboard --host 127.0.0.1 --port 8642
   ```

   Exemple Caddy :

   ```
   client.levolia.ai {
       reverse_proxy 127.0.0.1:8642
   }
   ```

5. Sur le poste du client, lancer Levolia Desktop, saisir l'adresse
   `https://<client>.levolia.ai` et le jeton, tester, appliquer.

L'app conserve la connexion dans son dossier de données utilisateur
(`connections.json`). Les variables `HERMES_DESKTOP_REMOTE_URL` et
`HERMES_DESKTOP_REMOTE_TOKEN` restent utilisables comme solution de secours.

## Reste à faire

- Remplacer le logo provisoire : `apps/desktop/assets/icon.{icns,ico,png}`,
  `apps/desktop/public/` et le composant `brand-mark.tsx`.
- Signature et notarisation des binaires (certificats Apple Developer et Windows).
- Mécanisme de mise à jour de l'app : il pointe encore vers le dépôt Nous Research
  (`apps/desktop/electron/update-remote.ts`). À rediriger vers un dépôt Levolia ou à désactiver.
- Traduction française de l'interface : le desktop n'embarque que en, ar et ja.
- Masquer dans les réglages les entrées « Nous Cloud » et « installation locale »
  qui ne concernent pas les clients Levolia.
