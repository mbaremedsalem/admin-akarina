# Agharina — API DRF (vente & location immobilière)

Système Django REST Framework complet, structuré en apps indépendantes.

## Démarrage rapide

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Admin Django : `http://127.0.0.1:8000/admin/`
- API : `http://127.0.0.1:8000/api/`

## Organisation des apps

| App | Rôle |
|---|---|
| `comptes` | Utilisateur custom, code/lien d'invitation, points de fidélité |
| `localisation` | `Ville` et `Quartier`, liés à chaque bien |
| `immobilier` | `Bien` (cœur du système), équipements, médias, calendrier |
| `transactions` | Vente/location finalisée, déclenche points + blocage calendrier |
| `fidelite` | Cadeaux échangeables contre les points |
| `offres` | "Panier" des publicités/offres créées par Agharina |

## Modèle `Bien` (immobilier)

Un seul modèle central couvre les 5 types (`type_bien`) : `ceremonie`,
`duplexe`, `appartement`, `terrain`, `commercial` — vendu ou loué
(`type_transaction`). Champs communs : meublé, chambres, salles de bain,
étages, prix (`unite_prix` = jour / 3jours / mois / forfait), description,
latitude/longitude, ville + quartier, nombre de propriétaires, gestionnaire,
équipements (M2M libre : caméra, piscine, garage, chambre gardien, balcon…).

Les spécificités par type sont déportées dans des modèles liés en 1-1,
pour rester flexible sans polluer le modèle principal :
- `DetailCeremonie` (avec_service, capacité…)
- `DetailTerrain` (superficie, dimensions, titre foncier…)

Chaque bien a une **référence unique** auto-générée (`AGH-TER-96EC5E5D`)
qui permet de retrouver toutes ses infos : `GET /api/biens/<reference>/`.

`MediaBien` permet d'attacher un nombre illimité de photos **et/ou vidéos**
à un bien (`type_media` = image/vidéo).

`Indisponibilite` est le calendrier : par défaut un bien est disponible,
le gestionnaire bloque des périodes (1 jour, plusieurs jours, un ou
plusieurs mois). La disponibilité est filtrable via
`?disponible_du=YYYY-MM-DD&disponible_au=YYYY-MM-DD`.

## Parrainage & fidélité

Chaque utilisateur a un `code_invitation` unique → `lien_invitation`
(`https://agharina.com/invite/<code>`). À l'inscription (`POST
/api/inscription/`), le champ `code_parrain` rattache le nouveau compte
à son parrain (`invite_par`).

Quand une `Transaction` (vente ou location) passe au statut `confirmee`,
un signal (`transactions/signals.py`) :
1. crédite automatiquement des points de fidélité au parrain du client
   (une seule fois, protégé par `points_attribues`) ;
2. si c'est une location, bloque automatiquement la période réservée
   dans le calendrier du bien.

Les points s'échangent contre un `Cadeau` (objet ou argent) via
`POST /api/echanges-cadeaux/`.

## Offres / "panier"

`Offre` regroupe les publicités et promotions créées par Agharina,
générales ou ciblées sur un bien précis, avec période de validité.
Lecture publique, écriture réservée au staff.

## Principaux endpoints

```
POST   /api/inscription/                 Créer un compte (+ code_parrain optionnel)
POST   /api/connexion/                   Obtenir un token (username/password)
GET    /api/profil/                      Profil + lien d'invitation
GET    /api/mes-points/                  Solde + historique de points

GET    /api/villes/  /api/quartiers/

GET    /api/biens/?type_bien=terrain&ville=1&prix_min=...&prix_max=...
GET    /api/biens/<reference>/           Fiche complète via la référence
POST   /api/biens/                       Créer un bien (gestionnaire connecté)
POST   /api/medias/                      Ajouter photo/vidéo à un bien
GET    /api/indisponibilites/?bien=1     Calendrier d'un bien
POST   /api/indisponibilites/            Bloquer une période

POST   /api/transactions/                Finaliser une vente/location
GET    /api/cadeaux/  POST /api/echanges-cadeaux/
GET    /api/offres/                      Offres/pub actives (panier)
```

## Extensibilité

- Ajouter un équipement : simple ligne dans l'admin (`Equipement`), pas
  de migration nécessaire.
- Ajouter un nouveau type de bien avec des champs propres : ajouter un
  modèle `DetailXxx` en 1-1 avec `Bien`, sur le même principe que
  `DetailTerrain`/`DetailCeremonie`.
