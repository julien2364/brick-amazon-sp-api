# HANDOFF — job qui écrase les prix Amazon.pl (05/11/2026)

## RÉSULTAT

**Le job est absent des deux dépôts.** Aucun code ne pousse de prix vers Amazon, ni dans
`julien2364/brick-amazon-sp-api`, ni dans `julien2364/arbitrage`.

Preuves (recherche du 05/11/2026) :

- `brick-amazon-sp-api` est la bibliothèque `python-amazon-sp-api` (saleweaver) sans code
  métier. Les seules occurrences de `patch_listings_item` / `put_listings_item`,
  `JSON_LISTINGS_FEED`, `POST_PRODUCT_PRICING_DATA` et `A1C3SOZRARQ6R3` sont les
  définitions de la bibliothèque (`sp_api/api/listings_items/*.py`,
  `sp_api/base/feedTypes.py:5` et `:9`, `sp_api/base/marketplaces.py:20` et `:70`) et ses
  tests à blanc. Aucun commit de julien2364 sur `master` ; une seule branche à lui :
  `fix/garde-fou-prix-marketplace` (PR brouillon #1, garde-fou seul, pas de job).
- `arbitrage` (698 commits, toutes branches, plus les 7 archives `.zip` décompressées) :
  aucun appel `listings/2021-08-01/items`, `feeds/2021-06-30`, `purchasable_offer`,
  `our_price` ni `POST_PRODUCT_PRICING_DATA`. Les appels SP-API sont **en lecture
  seule** : `arb-app/src/lib/spapi.ts:357` et `:364`, `tools/spapi_resolve_ean.py:278` et
  `:281` (`/products/pricing/v0/items`, `/batches/products/pricing/v0/itemOffers`). Les
  `× 100` et `/ 100` trouvés sont des pourcentages de marge et la conversion des centimes
  Keepa (`app/connectors/keepa-parse.ts:79`, `arb-app/src/lib/keepa.ts:321`), jamais un
  envoi vers Amazon. Aucune table catégorie → prix ; les `150` sont des filtres de
  recherche Keepa (`priceMax: 150`) ou des données fictives.
- Aucun secret en clair vu : `credentials.yml` (brick) a des champs vides.

Livré à la place (tâche 3) : le **garde-fou réutilisable** dans la bibliothèque SP-API,
point de passage naturel d'un job Python qui écrirait des prix. Pas dans `arbitrage`, qui
ne pousse aucun prix (et où un autre agent travaille).

- `sp_api/util/price_guard.py` : `prix_pl()` (règle), `verifier_prix_pl()` (garde-fou),
  `classer_anomalie()` (audit A_x100 / B_prix_fixe), `controler_prix()` (générique).
- `tests/util/test_price_guard.py` : 21 tests.

Règle appliquée : prix PL = max(prix FR ; 15 €) × taux BCE EUR/PLN, en zł (pas en grosz),
arrondi au centime (ROUND_HALF_UP). Refus si prix > 3 × la référence ou < 66,06 zł.

## VALIDATION

```
$ python -m pytest -q tests/util
.....................                                                    [100%]
21 passed
```

- Cas **12 615 zł** (prix FR 28,65 €, taux 4,404 → référence 126,17 zł) : **refusé**
  (`PriceRejected : 12615 > 3 × la référence 126.17`) et classé `A_x100`. Idem 14 107 et
  14 786 zł. Les mêmes montants divisés par 100 passent.
- Plancher : 66,06 zł accepté, 66,05 zł refusé ; 9,99 € → 66,06 zł.
- Suite complète : 136 échecs **préexistants et identiques** avant/après (tests qui
  exigent des identifiants AWS/LWA absents du conteneur) ; aucun nouvel échec.

## ÉTAT EXACT

- Dépôt `julien2364/brick-amazon-sp-api`, branche `claude/correctif-prix-pl-20261105`,
  construite **sur** `fix/garde-fou-prix-marketplace` (PR #1) : elle la contient et la
  remplace. PR brouillon ouverte vers `master`, **non fusionnée**.
- Compatibilité PR #1 gardée : `foreign_price()` et `check_price()` ont la même signature.
  Le test de la PR #1 nommé « …150_zl_refuse… » qui vérifiait en fait une acceptation a été
  renommé et corrigé.
- Rien écrit dans `arbitrage` (clone miroir en lecture dans le bac à sable seulement).
- Aucun appel à l'API Amazon, aucune soumission.

## LIMITES

- **Le job n'est pas trouvé** : le garde-fou ne protège que le code qui l'appelle. Il
  n'arrête pas un outil extérieur.
- **Groupe B (150 zł fixe) non bloqué par le garde-fou seul** : 150 zł est souvent entre
  66,06 zł et 3 × la référence. Il est repéré par `classer_anomalie()` et corrigé par le
  recalcul `prix_pl()`, pas par `verifier_prix_pl()`.
- Plancher **fixe** à 66,06 zł (= 15 € × 4,404) : si le taux BCE passe sous 4,404, les
  articles au plancher seront **refusés** (choix volontaire : bloquer plutôt que brader).
  À revoir si la règle doit suivre le taux du jour.
- Le taux BCE n'est pas récupéré par le module : l'appelant le fournit.

## SUITE

Pistes restantes pour trouver le job, par ordre de probabilité :

1. **Règle de prix automatique de Seller Central** (Tarification → Automatiser la
   tarification, marché PL) : une règle « prix fixe » ou « min/max » saisie en grosz
   donnerait exactement 150 zł et des ×100. Vérifier l'historique des règles et le
   journal « Tarification » des SKU 12 615 / 14 107 / 14 786 zł.
2. **Repricer externe** connecté au compte (BQool, RepricerExpress, Aura, SellerSnap,
   etc.) : Seller Central → Applications et services → Gérer vos applications ; révoquer
   ou suspendre ceux qui ont accès au PL. Vérifier aussi la **Tarification
   internationale / Construire des offres internationales** (synchronisation FR → PL avec
   règle de change), qui pousse des prix sans code chez nous.
3. **Script sur VPS** (Hetzner ou autre) : `crontab -l`, `systemctl list-timers`,
   `grep -rn "A1C3SOZRARQ6R3\|patch_listings_item\|purchasable_offer"` dans les dossiers
   personnels ; le rapport « Feed Processing » / l'historique des téléchargements de
   Seller Central montre si les prix arrivent par feed ou par l'API Listings, et avec quel
   identifiant d'application.
4. Une fois l'auteur trouvé : brancher `verifier_prix_pl()` juste avant l'appel
   d'écriture, et republier les prix avec `prix_pl()`.
