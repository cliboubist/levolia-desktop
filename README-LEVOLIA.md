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
- `apps/desktop/electron/main.ts` : schéma de lien profond aligné (`levolia`, `levolia-dev`) ;
  auto-mise à jour désactivée (`LEVOLIA_SELF_UPDATE_DISABLED`) et entrée de menu
  « Check for Updates » retirée. Les nouvelles versions passent par les installeurs Levolia.
  Le mode local reste disponible (nécessaire pour le computer use sur le poste) :
  au premier lancement, le formulaire distant est proposé en premier et un bouton
  « Installer Levolia en local » lance l'installation sur la machine.
- `apps/desktop/assets/icon.{png,icns,ico}`, `public/apple-touch-icon.png`,
  `public/levolia-mark.png`, `public/levolia-logo.png` : icônes générées depuis le logo Levolia.
- `apps/desktop/src/components/brand-mark.tsx` : logo Levolia dans l'interface.
- `apps/desktop/src/components/desktop-install-overlay.tsx` : le premier lancement
  affiche directement le formulaire de connexion distante, avec l'installation
  locale en action secondaire.
- `apps/desktop/src/components/first-run-remote-form.tsx` : bouton Retour masquable.
- `apps/desktop/src/app/settings/gateway-settings.tsx` et `connections-registry.tsx` :
  modes « local », « serveur distant » et « SSH ». Nous Cloud est masqué.
- `apps/desktop/src/i18n/fr.ts` : locale française (partielle : accueil, connexion,
  démarrage, actions communes ; le reste retombe sur l'anglais). Sélectionnée
  automatiquement sur un système en français.
- `apps/desktop/src/i18n/{en,ar,ja,zh,zh-hant,ru}.ts` : « Hermes » remplacé par
  « Levolia » dans les textes visibles. Les mentions « Nous Cloud » sont conservées.
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

- Signature et notarisation des binaires (certificats Apple Developer et Windows).
  Le script `scripts/notarize.mjs` attend les identifiants Apple en variables d'environnement.
- Compléter la traduction française au-delà des écrans d'accueil et de connexion.
- Construire et tester un installeur réel sur macOS et Windows contre un VPS de démonstration.

## Suivre les évolutions de Nous Research

Le dépôt a deux remotes : `origin` (votre dépôt) et `upstream` (Nous Research).
La branche `main` suit `upstream/main` à l'identique ; la branche `levolia`
porte les modifications Levolia.

Pour intégrer une nouvelle version amont :

```bash
bash scripts/levolia/sync-upstream.sh
```

Le script fusionne `main` dans `levolia`. Les fichiers de textes (locales et
tests de chaînes) sont pris tels quels chez Nous Research puis rebrandés par
`scripts/levolia/rebrand.py`, qui est rejouable à volonté. Seuls les conflits
sur du code structurel demandent une résolution manuelle ; ils sont listés en
sortie. Ensuite :

```bash
npm install
cd apps/desktop && npm run typecheck && npm run test:ui
```

Points de vigilance à chaque synchronisation :

- Vérifier que la garde `LEVOLIA_SELF_UPDATE_DISABLED` dans `apps/desktop/electron/main.ts`
  est toujours en place.
- Relancer l'app construite sur un profil vierge : elle doit s'arrêter sur le
  formulaire de connexion distante, avec le bouton d'installation locale.
- Mettre à jour l'agent sur les VPS clients avec la même version amont, car
  l'app contrôle l'écart de version avec le serveur.
- Compléter `apps/desktop/src/i18n/fr.ts` si de nouveaux écrans sont apparus.
