
# PHASE 3 - Collecte des vérifications VIES

from pathlib import Path
import pandas as pd
import time
import requests
import datetime
import logging
import json

# Définir les chemins des fichiers
dossier_projet = Path(__file__).resolve().parent.parent
chemin_csv = dossier_projet / "notebook" / "echantillon_200.csv"
chemin_resultats = dossier_projet / "api" / "resultats_vies.csv"
chemin_logs = dossier_projet / "api" / "collecte_vies.log"

# Configurer le journal des événements
logging.basicConfig(
    filename=chemin_logs,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

# Charger les 200 numéros de TVA
echantillon = pd.read_csv(chemin_csv, dtype=str)
numeros = echantillon["numero_final"]

# Modifier cette valeur pour tester 3, 20 ou 200 numéros
taille_echantillon = 3

# Définir la pause entre les appels VIES
delai = 2

# Charger les résultats déjà enregistrés
if chemin_resultats.exists():
    df_existants = pd.read_csv(chemin_resultats, dtype=str)
    resultats_vies = df_existants.to_dict("records")
else:
    resultats_vies = []

# Identifier les numéros déjà vérifiés avec succès
numeros_reussis = set()

for resultat in resultats_vies:
    if (
        str(resultat.get("erreur_vies")) in ("VALID", "INVALID")
        and str(resultat.get("code_http")) == "200"
        and str(resultat.get("valide_vies")).lower() in ("true", "false")
    ):
        numeros_reussis.add(str(resultat["numero_final"]))

# Démarrer la collecte
logging.info("Début de la collecte VIES")
print("Début de la collecte VIES")

# Parcourir les numéros de l'échantillon
for numero_final in numeros.head(taille_echantillon):

    # Ne pas rappeler VIES pour un numéro déjà vérifié
    if numero_final in numeros_reussis:
        logging.info("Numéro ignoré (déjà vérifié) : %s", numero_final)
        print("Déjà vérifié :", numero_final)
        continue

    # Récupérer le préfixe et le numéro de TVA
    pays = numero_final[:2]
    tva = numero_final[2:]

    # Construire l'URL de l'API VIES
    url = f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{pays}/vat/{tva}"

    # Initialiser les variables
    debut = time.perf_counter()
    code_http = None
    erreur_vies = None
    valide_vies = None
    donnees = None
    erreur_technique = None

    try:
        # Envoyer la requête à VIES
        reponse = requests.get(url, timeout=10)
        code_http = reponse.status_code

        # Vérifier le statut HTTP et récupérer le JSON
        reponse.raise_for_status()
        donnees = reponse.json()

        # Récupérer le message VIES
        erreur_vies = donnees.get("userError")

        # Ne retenir la validité que si VIES a répondu
        if erreur_vies in ("VALID", "INVALID"):
            valide_vies = donnees.get("isValid")

        # Vérifier que la réponse est cohérente
        if (
            erreur_vies in ("VALID", "INVALID")
            and isinstance(valide_vies, bool)
        ):
            numeros_reussis.add(numero_final)
        else:
            erreur_technique = (
                f"Réponse VIES non concluante : {erreur_vies}"
            )

    except (requests.exceptions.RequestException, ValueError) as erreur:
        # Conserver les erreurs réseau, HTTP ou JSON
        erreur_technique = str(erreur)
        print("Erreur technique :", erreur)

    finally:
        # Calculer la durée de l'appel
        duree = time.perf_counter() - debut

    # Enregistrer la date et l'heure
    date_verification = datetime.datetime.now().isoformat(
        timespec="seconds"
    )

    # Préparer le résultat de cet appel
    resultat = {
        "numero_final": numero_final,
        "pays": pays,
        "code_http": code_http,
        "erreur_vies": erreur_vies,
        "valide_vies": valide_vies,
        "duree": duree,
        "date": date_verification,
        "erreur_technique": erreur_technique,
        "reponse_complete": (
            json.dumps(donnees, ensure_ascii=False)
            if donnees is not None
            else None
        )
    }

    # Ajouter le résultat à la liste
    resultats_vies.append(resultat)

    # Sauvegarder immédiatement après chaque appel
    df_resultats = pd.DataFrame(resultats_vies)
    df_resultats.to_csv(chemin_resultats, index=False)

    # Journaliser le statut et la durée
    logging.info(
        "TVA=%s HTTP=%s durée=%.3fs résultat=%s erreur=%s",
        numero_final,
        code_http,
        duree,
        erreur_vies,
        erreur_technique
    )

    print(
        numero_final,
        "| HTTP :", code_http,
        "| VIES :", erreur_vies,
        "| Durée :", round(duree, 3), "s"
    )

    # Attendre avant le prochain appel
    time.sleep(delai)

# Terminer la collecte
logging.info("Fin de la collecte VIES")
print("Fin de la collecte VIES")

# Afficher les résultats
df_resultats = pd.DataFrame(resultats_vies)
print(df_resultats)
