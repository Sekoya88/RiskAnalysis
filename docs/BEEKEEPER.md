# Connexion Beekeeper Studio → PostgreSQL (RiskAnalysis Docker)

Ces valeurs correspondent au `docker-compose.yml` du repo et à `.env` (`POSTGRES_PORT_PUBLISH` + `DATABASE_URL`).

| Champ | Valeur typique |
|--------|----------------|
| **Host** | `127.0.0.1` ou `localhost` |
| **Port** | `15432` (défaut actuel ; si tu as changé `POSTGRES_PORT_PUBLISH`, utilise ce port) |
| **User** | `risk` |
| **Password** | `riskpass` (ou la valeur de `POSTGRES_PASSWORD` si tu l’as surchargée) |
| **Database** | `riskanalysis` |

**URL / URI** (onglet « Import from URL » dans Beekeeper) :

```text
postgresql://risk:riskpass@127.0.0.1:15432/riskanalysis
```

Vérifie que le conteneur tourne : `docker compose ps` → `risk-postgres` **Up**.

> Si tu vois encore `localhost:5433` dans Beekeeper, c’est une **autre** instance Postgres (pas ce projet). Utilise le port mappé par **ce** compose (`15432` par défaut).
