# Plateforme Contrats d’Apprentissage – Intégrale Academy (Noir & Or)

Public: `/` (formulaire complet)
Admin: `/admin` (mot de passe requis)
Persistance: `/data/contracts.json`
Design: charte noir & or avec logo intégré.

## Notification des nouveaux contrats

Après l'enregistrement d'un formulaire public, l'application envoie un e-mail à
`aurelie@integraleacademy.com` pour signaler qu'un contrat d'apprentissage est
à traiter. Configurez le serveur SMTP au moyen des variables d'environnement
suivantes :

- `SMTP_HOST` : hôte SMTP (obligatoire pour activer l'envoi) ;
- `SMTP_PORT` : port SMTP, `587` par défaut ;
- `SMTP_USERNAME` et `SMTP_PASSWORD` : identifiants SMTP, si nécessaires ;
- `SMTP_FROM` : adresse de l'expéditeur ;
- `SMTP_USE_TLS` : `true` par défaut ; définissez `false` si le serveur ne
  prend pas en charge STARTTLS.

Si l'envoi échoue ou si `SMTP_HOST` n'est pas renseigné, le contrat reste bien
enregistré et l'erreur est consignée dans les logs de l'application.
