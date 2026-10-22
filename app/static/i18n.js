// Traductions de l'interface : français, néerlandais, anglais.
// Les noms des couleurs, vêtements et armes viennent du serveur (/api/i18n).
const I18N = {
  fr: {
    lang_label: "Langue",
    tab_live: "Direct", tab_events: "Événements", tab_faces: "Visages", tab_settings: "Paramètres",
    engine_device: "Calcul : {d}", faces_ok: "visages ✓", faces_missing: "visages ✗ (modèles absents)",
    weapons_model: "armes : modèle spécialisé ({c})", weapons_coco: "armes : couteaux/ciseaux/battes seulement",
    cams_title: "Caméras", cams_all: "Toutes", cams_none: "Aucune", cams_count: "{n}/{total} affichées",
    cams_solo_title: "Afficher seulement celle-ci",
    no_selected: "Aucune caméra sélectionnée. Cochez-en une dans la colonne de gauche.",
    btn_areas: "Zones", btn_areas_title: "Zones et lignes de comptage",
    areas_title: "Zones et lignes : {name}", tool_zone: "+ Zone", tool_line: "+ Ligne", tool_finish: "Terminer la zone",
    hint_idle: "Choisissez « + Zone » ou « + Ligne », puis cliquez sur l'image. Les personnes sont repérées par leurs pieds.",
    hint_zone: "Cliquez pour placer les coins de la zone. Cliquez sur le premier point (ou Entrée) pour la fermer. Échap pour annuler.",
    hint_line: "Cliquez sur les deux extrémités de la ligne. La flèche indique le sens compté comme « entrée ».",
    default_zone: "Zone {n}", default_line: "Ligne {n}", kind_zone: "Zone", kind_line: "Ligne",
    zone_alert: "Alerte au-delà de", people: "personnes", invert: "Inverser le sens",
    reset_counts: "Remettre à zéro", confirm_reset: "Remettre les compteurs de « {name} » à zéro ?",
    no_areas: "Aucune zone ni ligne. Dessinez-en une sur l'image.",
    count_zone: "{inside} présente(s) · max {max}", count_line: "{in} entrées · {out} sorties", since: "depuis le {date}",
    ev_zone: "Zone trop pleine", f_zones: "Zones trop pleines", people_n: "{n} personnes", toast_zone: "👥 {name} : {n} personnes",
    add_camera: "+ Ajouter une caméra", layout: "Disposition",
    no_cam: "Aucune caméra. Cliquez sur « Ajouter une caméra ».",
    btn_clothes: "Vêtements", btn_clothes_title: "Type et couleur des vêtements",
    btn_faces: "Visages", btn_faces_title: "Reconnaissance faciale",
    btn_weapons: "Armes", btn_weapons_title: "Détection d'armes",
    delete: "Supprimer", confirm_delete_cam: "Supprimer la caméra « {name} » ?",
    st_online: "en ligne", st_offline: "hors ligne", st_connecting: "connexion", st_reconnecting: "reconnexion",
    st_starting: "démarrage", fps: "{n} img/s",
    f_all_types: "Tous les types", f_weapons: "Armes", f_faces: "Visages reconnus", f_persons: "Personnes (vêtements)",
    f_all_cams: "Toutes les caméras", f_upper_type: "Haut : tous types", f_upper_color: "Haut : toutes couleurs",
    f_lower_type: "Bas : tous types", f_lower_color: "Bas : toutes couleurs", f_label_ph: "Nom / objet…",
    search: "Rechercher", clear_journal: "Vider le journal",
    confirm_clear: "Supprimer tous les événements et captures ?",
    ev_weapon: "Arme détectée", ev_face: "Visage reconnu", ev_person: "Personne",
    confidence: "confiance {n} %", top: "Haut", bottom: "Bas", no_events: "Aucun événement.",
    toast_weapon: "⚠ ARME : {label}",
    faces_off: "La reconnaissance faciale est désactivée dans les Paramètres : les visages sont détectés mais personne n'est identifié.",
    enroll_title: "Enregistrer une personne",
    enroll_help: "Une photo nette de face par envoi. Ajoutez plusieurs photos d'une même personne pour améliorer la reconnaissance.",
    name_ph: "Nom", save: "Enregistrer", photos: "{n} photo(s)", no_faces: "Aucune personne enregistrée.",
    confirm_delete_face: "Supprimer {name} ?", analysing: "Analyse…", enrolled: "✓ {name} enregistré(e)",
    no_change: "Aucun changement.", saved: "✓ Enregistré.",
    reloading: "Rechargement des modèles…", reloading_sub: "Les caméras redémarrent dans quelques secondes.",
    new_cam: "Nouvelle caméra", cam_name: "Nom", cam_name_ph: "Entrée principale", cam_source: "Source",
    source_help: "Webcam locale : <code>0</code>, <code>1</code>… · IP : <code>rtsp://…</code> ou <code>http://…/video.mjpg</code> · Fichier : <code>C:\\videos\\test.mp4</code>",
    chk_clothes: "Vêtements (type et couleur)", chk_faces: "Reconnaissance faciale", chk_weapons: "Détection d'armes",
    max_fps_label: "Images analysées / s max", cancel: "Annuler", add: "Ajouter",
    // paramètres
    sec_compute: "Calcul", sec_privacy: "Vie privée et RGPD", sec_detection: "Détection", sec_display: "Vêtements et affichage",
    s_device: "Processeur utilisé pour l'analyse", s_device_auto: "Automatique (GPU si disponible)",
    s_device_gpu: "GPU : {name}", s_device_nogpu: "GPU (non détecté)", s_device_cpu: "CPU (processeur)",
    s_device_help: "Actuellement : {cur}. Le CPU est bien plus lent mais libère la carte graphique. Changer recharge les modèles (environ 20 s).",
    s_max_fps: "Images analysées par seconde (par défaut)",
    s_max_fps_help: "Pour les nouvelles caméras ; chaque caméra garde son propre réglage.",
    s_face_rec: "Reconnaissance faciale (identification)",
    s_face_rec_help: "Donnée biométrique : à n'activer qu'avec le consentement explicite des personnes enregistrées.",
    s_face_rec_confirm: "La reconnaissance faciale traite des données biométriques (art. 9 RGPD).\n\nElle n'est permise qu'avec une exception légale, par exemple le consentement explicite et libre de chaque personne enregistrée.\n\nActiver quand même ?",
    s_blur: "Flouter les visages non reconnus",
    s_blur_help: "Dans le direct et dans les captures du journal. Recommandé si des tiers passent devant la caméra.",
    s_log_unknown: "Enregistrer aussi les visages inconnus dans le journal",
    s_retention: "Durée de conservation du journal (jours)",
    s_retention_help: "Événements et captures plus anciens supprimés automatiquement (vérifié chaque heure). 0 = jamais.",
    s_retention_warn: "La loi caméras prévoit en principe 1 mois maximum, sauf preuve d'un incident.",
    s_privacy_reread: "Relire l'avertissement RGPD", s_privacy_acked: "Pris connaissance le {date}.", s_privacy_not: "Pas encore validé.",
    s_person_conf: "Confiance minimale : personnes",
    s_weapon_conf: "Confiance minimale : armes à feu",
    s_weapon_conf_help: "Plus haut = moins de fausses alertes (téléphones…), mais risque de rater une arme.",
    s_weapon_types: "Préciser le type d'arme à feu (pistolet, revolver, fusil…)",
    s_weapon_types_help: "Par CLIP. Mesuré : 76 % des pistolets et 94 % des fusils classés dans la bonne famille.",
    s_weapon_verify: "Écarter les fausses alertes (téléphone, bouteille…)",
    s_weapon_verify_help: "CLIP vérifie chaque arme détectée. Mesuré : 15 fausses alertes sur 15 écartées, 2 % des vraies armes perdues.",
    s_verify_th: "Certitude requise pour écarter une alerte",
    s_verify_th_help: "Plus haut = n'écarte que les cas évidents (moins de vraies armes perdues).",
    s_coco_conf: "Confiance minimale : couteaux, ciseaux, battes",
    s_face_th: "Seuil de reconnaissance des visages",
    s_face_th_help: "Plus haut = plus strict (moins de confusions, plus d'« Inconnu »).",
    s_weapon_cd: "Délai entre deux alertes d'arme identiques (s)",
    s_face_cd: "Délai entre deux alertes de visage identiques (s)",
    s_clothing: "Reconnaître le type de vêtements (jean, pull…)",
    s_clothing_help: "Utilise le modèle CLIP. Changer recharge les modèles.",
    s_clothing_conf: "Confiance minimale du type de vêtement", s_clothing_conf_help: "En dessous, le type affiché est « ? ».",
    s_draw: "Personnes et objets", s_draw_box: "Carrés", s_draw_contour: "Contours (silhouette)",
    s_draw_help: "Les contours sont plus lents. Changer recharge les modèles.",
    s_face_shape: "Visages", s_shape_oval: "Ovale", s_shape_box: "Carré",
    s_overlay_lang: "Langue des textes sur la vidéo",
    s_overlay_lang_help: "Textes incrustés dans l'image et dans les captures du journal (la même pour tous les utilisateurs).",
    // RGPD
    privacy_title: "Vidéosurveillance et vie privée",
    privacy_intro: "Cette application filme des personnes et peut les identifier par leur visage. En Belgique et dans l'UE, plusieurs règles s'appliquent selon l'usage :",
    privacy_list: `<li><b>Loi caméras (21 mars 2007)</b> : déclarer chaque caméra sur
        <a href="https://www.declarationcamera.be" target="_blank" rel="noopener">declarationcamera.be</a>
        (sauf usage personnel et domestique à l'intérieur d'une habitation privée), apposer le pictogramme
        d'avertissement, tenir un registre des traitements d'images, ne pas filmer la voie publique ni chez les voisins.</li>
      <li><b>Durée de conservation</b> : en principe 1 mois maximum, sauf si les images servent de preuve
        d'une infraction ou d'un dommage. Réglable dans les Paramètres.</li>
      <li><b>Reconnaissance faciale = donnée biométrique</b> (art. 9 RGPD) : interdite par principe, sauf exception
        comme le consentement explicite et libre de chaque personne enregistrée. Ne l'utilisez pas pour identifier
        des visiteurs, clients ou passants.</li>
      <li><b>Au travail</b> : filmer des employés est encadré (CCT n° 68) : information préalable et finalité légitime.</li>
      <li><b>Personnes filmées</b> : elles ont un droit d'accès à leurs images et peuvent demander leur effacement.</li>`,
    privacy_disclaimer: `Ce rappel n'est pas un avis juridique. En cas de doute, consultez l'Autorité de protection des données
      (<a href="https://www.autoriteprotectiondonnees.be" target="_blank" rel="noopener">autoriteprotectiondonnees.be</a>).`,
    privacy_check: "J'ai pris connaissance de ces obligations", privacy_ok: "J'ai compris",
  },

  nl: {
    lang_label: "Taal",
    tab_live: "Live", tab_events: "Gebeurtenissen", tab_faces: "Gezichten", tab_settings: "Instellingen",
    engine_device: "Rekenen: {d}", faces_ok: "gezichten ✓", faces_missing: "gezichten ✗ (modellen ontbreken)",
    weapons_model: "wapens: gespecialiseerd model ({c})", weapons_coco: "wapens: alleen messen/scharen/knuppels",
    cams_title: "Camera's", cams_all: "Alle", cams_none: "Geen", cams_count: "{n}/{total} getoond",
    cams_solo_title: "Alleen deze tonen",
    no_selected: "Geen camera geselecteerd. Vink er een aan in de linkerkolom.",
    btn_areas: "Zones", btn_areas_title: "Telzones en -lijnen",
    areas_title: "Zones en lijnen: {name}", tool_zone: "+ Zone", tool_line: "+ Lijn", tool_finish: "Zone afsluiten",
    hint_idle: "Kies « + Zone » of « + Lijn » en klik dan op het beeld. Personen worden gevolgd aan hun voeten.",
    hint_zone: "Klik om de hoeken van de zone te plaatsen. Klik op het eerste punt (of Enter) om ze te sluiten. Esc om te annuleren.",
    hint_line: "Klik op de twee uiteinden van de lijn. De pijl geeft de richting aan die als « in » telt.",
    default_zone: "Zone {n}", default_line: "Lijn {n}", kind_zone: "Zone", kind_line: "Lijn",
    zone_alert: "Alarm boven", people: "personen", invert: "Richting omkeren",
    reset_counts: "Op nul zetten", confirm_reset: "De tellers van « {name} » op nul zetten?",
    no_areas: "Nog geen zones of lijnen. Teken er een op het beeld.",
    count_zone: "{inside} aanwezig · max {max}", count_line: "{in} in · {out} uit", since: "sinds {date}",
    ev_zone: "Zone te vol", f_zones: "Te volle zones", people_n: "{n} personen", toast_zone: "👥 {name}: {n} personen",
    add_camera: "+ Camera toevoegen", layout: "Indeling",
    no_cam: "Geen camera's. Klik op « Camera toevoegen ».",
    btn_clothes: "Kleding", btn_clothes_title: "Soort en kleur van de kleding",
    btn_faces: "Gezichten", btn_faces_title: "Gezichtsherkenning",
    btn_weapons: "Wapens", btn_weapons_title: "Wapendetectie",
    delete: "Verwijderen", confirm_delete_cam: "Camera « {name} » verwijderen?",
    st_online: "online", st_offline: "offline", st_connecting: "verbinden", st_reconnecting: "opnieuw verbinden",
    st_starting: "opstarten", fps: "{n} beelden/s",
    f_all_types: "Alle soorten", f_weapons: "Wapens", f_faces: "Herkende gezichten", f_persons: "Personen (kleding)",
    f_all_cams: "Alle camera's", f_upper_type: "Boven: alle soorten", f_upper_color: "Boven: alle kleuren",
    f_lower_type: "Onder: alle soorten", f_lower_color: "Onder: alle kleuren", f_label_ph: "Naam / voorwerp…",
    search: "Zoeken", clear_journal: "Logboek wissen",
    confirm_clear: "Alle gebeurtenissen en opnames verwijderen?",
    ev_weapon: "Wapen gedetecteerd", ev_face: "Gezicht herkend", ev_person: "Persoon",
    confidence: "zekerheid {n} %", top: "Boven", bottom: "Onder", no_events: "Geen gebeurtenissen.",
    toast_weapon: "⚠ WAPEN: {label}",
    faces_off: "Gezichtsherkenning staat uit in de Instellingen: gezichten worden gedetecteerd, maar niemand wordt geïdentificeerd.",
    enroll_title: "Een persoon registreren",
    enroll_help: "Eén scherpe foto van voren per keer. Voeg meerdere foto's van dezelfde persoon toe voor een betere herkenning.",
    name_ph: "Naam", save: "Opslaan", photos: "{n} foto('s)", no_faces: "Nog niemand geregistreerd.",
    confirm_delete_face: "{name} verwijderen?", analysing: "Analyseren…", enrolled: "✓ {name} geregistreerd",
    no_change: "Geen wijzigingen.", saved: "✓ Opgeslagen.",
    reloading: "Modellen worden opnieuw geladen…", reloading_sub: "De camera's starten binnen enkele seconden opnieuw.",
    new_cam: "Nieuwe camera", cam_name: "Naam", cam_name_ph: "Hoofdingang", cam_source: "Bron",
    source_help: "Lokale webcam: <code>0</code>, <code>1</code>… · IP: <code>rtsp://…</code> of <code>http://…/video.mjpg</code> · Bestand: <code>C:\\videos\\test.mp4</code>",
    chk_clothes: "Kleding (soort en kleur)", chk_faces: "Gezichtsherkenning", chk_weapons: "Wapendetectie",
    max_fps_label: "Max. geanalyseerde beelden / s", cancel: "Annuleren", add: "Toevoegen",
    sec_compute: "Rekenkracht", sec_privacy: "Privacy en AVG", sec_detection: "Detectie", sec_display: "Kleding en weergave",
    s_device: "Processor voor de analyse", s_device_auto: "Automatisch (GPU indien beschikbaar)",
    s_device_gpu: "GPU: {name}", s_device_nogpu: "GPU (niet gevonden)", s_device_cpu: "CPU (processor)",
    s_device_help: "Nu: {cur}. De CPU is veel trager, maar ontlast de grafische kaart. Wijzigen laadt de modellen opnieuw (ongeveer 20 s).",
    s_max_fps: "Geanalyseerde beelden per seconde (standaard)",
    s_max_fps_help: "Voor nieuwe camera's; elke camera houdt zijn eigen instelling.",
    s_face_rec: "Gezichtsherkenning (identificatie)",
    s_face_rec_help: "Biometrische gegevens: alleen inschakelen met uitdrukkelijke toestemming van de geregistreerde personen.",
    s_face_rec_confirm: "Gezichtsherkenning verwerkt biometrische gegevens (art. 9 AVG).\n\nDat mag alleen met een wettelijke uitzondering, bijvoorbeeld de uitdrukkelijke en vrije toestemming van elke geregistreerde persoon.\n\nToch inschakelen?",
    s_blur: "Niet-herkende gezichten vervagen",
    s_blur_help: "In het livebeeld en in de opnames van het logboek. Aanbevolen als derden voor de camera komen.",
    s_log_unknown: "Ook onbekende gezichten in het logboek opslaan",
    s_retention: "Bewaartermijn van het logboek (dagen)",
    s_retention_help: "Oudere gebeurtenissen en opnames worden automatisch verwijderd (elk uur gecontroleerd). 0 = nooit.",
    s_retention_warn: "De camerawet voorziet in principe maximaal 1 maand, behalve als bewijs van een incident.",
    s_privacy_reread: "De privacywaarschuwing opnieuw lezen", s_privacy_acked: "Gelezen op {date}.", s_privacy_not: "Nog niet bevestigd.",
    s_person_conf: "Minimale zekerheid: personen",
    s_weapon_conf: "Minimale zekerheid: vuurwapens",
    s_weapon_conf_help: "Hoger = minder valse alarmen (telefoons…), maar meer kans om een wapen te missen.",
    s_weapon_types: "Soort vuurwapen bepalen (pistool, revolver, geweer…)",
    s_weapon_types_help: "Via CLIP. Gemeten: 76 % van de pistolen en 94 % van de geweren in de juiste groep ingedeeld.",
    s_weapon_verify: "Valse alarmen weren (telefoon, fles…)",
    s_weapon_verify_help: "CLIP controleert elk gedetecteerd wapen. Gemeten: 15 van de 15 valse alarmen geweerd, 2 % van de echte wapens gemist.",
    s_verify_th: "Vereiste zekerheid om een alarm te weren",
    s_verify_th_help: "Hoger = weert alleen duidelijke gevallen (minder echte wapens gemist).",
    s_coco_conf: "Minimale zekerheid: messen, scharen, knuppels",
    s_face_th: "Drempel voor gezichtsherkenning",
    s_face_th_help: "Hoger = strenger (minder verwisselingen, vaker « Onbekend »).",
    s_weapon_cd: "Wachttijd tussen twee identieke wapenalarmen (s)",
    s_face_cd: "Wachttijd tussen twee identieke gezichtsalarmen (s)",
    s_clothing: "Soort kleding herkennen (jeans, trui…)",
    s_clothing_help: "Gebruikt het CLIP-model. Wijzigen laadt de modellen opnieuw.",
    s_clothing_conf: "Minimale zekerheid voor de soort kleding", s_clothing_conf_help: "Daaronder wordt « ? » getoond.",
    s_draw: "Personen en voorwerpen", s_draw_box: "Kaders", s_draw_contour: "Contouren (silhouet)",
    s_draw_help: "Contouren zijn trager. Wijzigen laadt de modellen opnieuw.",
    s_face_shape: "Gezichten", s_shape_oval: "Ovaal", s_shape_box: "Kader",
    s_overlay_lang: "Taal van de teksten in het beeld",
    s_overlay_lang_help: "Teksten in het videobeeld en in de opnames van het logboek (dezelfde voor alle gebruikers).",
    privacy_title: "Camerabewaking en privacy",
    privacy_intro: "Deze toepassing filmt personen en kan ze aan hun gezicht herkennen. In België en de EU gelden, afhankelijk van het gebruik, meerdere regels:",
    privacy_list: `<li><b>Camerawet (21 maart 2007)</b>: elke camera aangeven via
        <a href="https://www.aangiftecamera.be" target="_blank" rel="noopener">aangiftecamera.be</a>
        (behalve voor persoonlijk en huiselijk gebruik binnen een privéwoning), het waarschuwingspictogram
        aanbrengen, een register van de beeldverwerkingen bijhouden, niet de openbare weg of de buren filmen.</li>
      <li><b>Bewaartermijn</b>: in principe maximaal 1 maand, behalve als de beelden een misdrijf of schade
        bewijzen. In te stellen bij Instellingen.</li>
      <li><b>Gezichtsherkenning = biometrische gegevens</b> (art. 9 AVG): in principe verboden, behalve bij een
        uitzondering zoals de uitdrukkelijke en vrije toestemming van elke geregistreerde persoon. Gebruik ze niet
        om bezoekers, klanten of voorbijgangers te identificeren.</li>
      <li><b>Op het werk</b>: werknemers filmen is gereglementeerd (cao nr. 68): voorafgaande informatie en een legitiem doel.</li>
      <li><b>Gefilmde personen</b>: zij hebben recht op toegang tot hun beelden en kunnen de verwijdering ervan vragen.</li>`,
    privacy_disclaimer: `Deze herinnering is geen juridisch advies. Raadpleeg bij twijfel de Gegevensbeschermingsautoriteit
      (<a href="https://www.gegevensbeschermingsautoriteit.be" target="_blank" rel="noopener">gegevensbeschermingsautoriteit.be</a>).`,
    privacy_check: "Ik heb kennisgenomen van deze verplichtingen", privacy_ok: "Begrepen",
  },

  en: {
    lang_label: "Language",
    tab_live: "Live", tab_events: "Events", tab_faces: "Faces", tab_settings: "Settings",
    engine_device: "Compute: {d}", faces_ok: "faces ✓", faces_missing: "faces ✗ (models missing)",
    weapons_model: "weapons: specialised model ({c})", weapons_coco: "weapons: knives/scissors/bats only",
    cams_title: "Cameras", cams_all: "All", cams_none: "None", cams_count: "{n}/{total} shown",
    cams_solo_title: "Show only this one",
    no_selected: "No camera selected. Tick one in the left column.",
    btn_areas: "Zones", btn_areas_title: "Counting zones and lines",
    areas_title: "Zones and lines: {name}", tool_zone: "+ Zone", tool_line: "+ Line", tool_finish: "Close the zone",
    hint_idle: "Choose « + Zone » or « + Line », then click on the image. People are tracked by their feet.",
    hint_zone: "Click to place the zone's corners. Click the first point (or press Enter) to close it. Esc to cancel.",
    hint_line: "Click both ends of the line. The arrow shows the direction counted as « in ».",
    default_zone: "Zone {n}", default_line: "Line {n}", kind_zone: "Zone", kind_line: "Line",
    zone_alert: "Alert above", people: "people", invert: "Reverse direction",
    reset_counts: "Reset", confirm_reset: "Reset the counters of « {name} »?",
    no_areas: "No zones or lines yet. Draw one on the image.",
    count_zone: "{inside} present · max {max}", count_line: "{in} in · {out} out", since: "since {date}",
    ev_zone: "Zone over capacity", f_zones: "Zones over capacity", people_n: "{n} people", toast_zone: "👥 {name}: {n} people",
    add_camera: "+ Add a camera", layout: "Layout",
    no_cam: "No cameras. Click « Add a camera ».",
    btn_clothes: "Clothing", btn_clothes_title: "Clothing type and colour",
    btn_faces: "Faces", btn_faces_title: "Face recognition",
    btn_weapons: "Weapons", btn_weapons_title: "Weapon detection",
    delete: "Delete", confirm_delete_cam: "Delete camera « {name} »?",
    st_online: "online", st_offline: "offline", st_connecting: "connecting", st_reconnecting: "reconnecting",
    st_starting: "starting", fps: "{n} fps",
    f_all_types: "All types", f_weapons: "Weapons", f_faces: "Recognised faces", f_persons: "People (clothing)",
    f_all_cams: "All cameras", f_upper_type: "Top: all types", f_upper_color: "Top: all colours",
    f_lower_type: "Bottom: all types", f_lower_color: "Bottom: all colours", f_label_ph: "Name / object…",
    search: "Search", clear_journal: "Clear the log",
    confirm_clear: "Delete all events and snapshots?",
    ev_weapon: "Weapon detected", ev_face: "Face recognised", ev_person: "Person",
    confidence: "confidence {n} %", top: "Top", bottom: "Bottom", no_events: "No events.",
    toast_weapon: "⚠ WEAPON: {label}",
    faces_off: "Face recognition is turned off in Settings: faces are detected but nobody is identified.",
    enroll_title: "Register a person",
    enroll_help: "One sharp front-facing photo per upload. Add several photos of the same person to improve recognition.",
    name_ph: "Name", save: "Save", photos: "{n} photo(s)", no_faces: "Nobody registered yet.",
    confirm_delete_face: "Delete {name}?", analysing: "Analysing…", enrolled: "✓ {name} registered",
    no_change: "No changes.", saved: "✓ Saved.",
    reloading: "Reloading models…", reloading_sub: "Cameras will restart in a few seconds.",
    new_cam: "New camera", cam_name: "Name", cam_name_ph: "Main entrance", cam_source: "Source",
    source_help: "Local webcam: <code>0</code>, <code>1</code>… · IP: <code>rtsp://…</code> or <code>http://…/video.mjpg</code> · File: <code>C:\\videos\\test.mp4</code>",
    chk_clothes: "Clothing (type and colour)", chk_faces: "Face recognition", chk_weapons: "Weapon detection",
    max_fps_label: "Max analysed frames / s", cancel: "Cancel", add: "Add",
    sec_compute: "Compute", sec_privacy: "Privacy and GDPR", sec_detection: "Detection", sec_display: "Clothing and display",
    s_device: "Processor used for analysis", s_device_auto: "Automatic (GPU if available)",
    s_device_gpu: "GPU: {name}", s_device_nogpu: "GPU (not detected)", s_device_cpu: "CPU (processor)",
    s_device_help: "Currently: {cur}. The CPU is much slower but frees the graphics card. Changing reloads the models (about 20 s).",
    s_max_fps: "Analysed frames per second (default)",
    s_max_fps_help: "For new cameras; each camera keeps its own setting.",
    s_face_rec: "Face recognition (identification)",
    s_face_rec_help: "Biometric data: only enable with the explicit consent of the registered people.",
    s_face_rec_confirm: "Face recognition processes biometric data (GDPR art. 9).\n\nIt is only allowed under a legal exception, for example the explicit and free consent of every registered person.\n\nEnable anyway?",
    s_blur: "Blur unrecognised faces",
    s_blur_help: "In the live view and in log snapshots. Recommended if third parties pass in front of the camera.",
    s_log_unknown: "Also log unknown faces",
    s_retention: "Log retention (days)",
    s_retention_help: "Older events and snapshots are deleted automatically (checked every hour). 0 = never.",
    s_retention_warn: "The Belgian Camera Act sets 1 month maximum in principle, unless the footage proves an incident.",
    s_privacy_reread: "Read the privacy notice again", s_privacy_acked: "Acknowledged on {date}.", s_privacy_not: "Not acknowledged yet.",
    s_person_conf: "Minimum confidence: people",
    s_weapon_conf: "Minimum confidence: firearms",
    s_weapon_conf_help: "Higher = fewer false alarms (phones…), but a higher risk of missing a weapon.",
    s_weapon_types: "Identify the firearm type (handgun, revolver, rifle…)",
    s_weapon_types_help: "Using CLIP. Measured: 76 % of handguns and 94 % of rifles put in the right family.",
    s_weapon_verify: "Filter out false alarms (phone, bottle…)",
    s_weapon_verify_help: "CLIP checks every detected weapon. Measured: 15 of 15 false alarms removed, 2 % of real weapons lost.",
    s_verify_th: "Certainty needed to discard an alarm",
    s_verify_th_help: "Higher = only discards obvious cases (fewer real weapons lost).",
    s_coco_conf: "Minimum confidence: knives, scissors, bats",
    s_face_th: "Face recognition threshold",
    s_face_th_help: "Higher = stricter (fewer mix-ups, more « Unknown »).",
    s_weapon_cd: "Delay between two identical weapon alerts (s)",
    s_face_cd: "Delay between two identical face alerts (s)",
    s_clothing: "Recognise clothing type (jeans, sweater…)",
    s_clothing_help: "Uses the CLIP model. Changing reloads the models.",
    s_clothing_conf: "Minimum confidence for clothing type", s_clothing_conf_help: "Below it, « ? » is shown.",
    s_draw: "People and objects", s_draw_box: "Boxes", s_draw_contour: "Outlines (silhouette)",
    s_draw_help: "Outlines are slower. Changing reloads the models.",
    s_face_shape: "Faces", s_shape_oval: "Oval", s_shape_box: "Box",
    s_overlay_lang: "Language of the text on the video",
    s_overlay_lang_help: "Text drawn on the video and on log snapshots (the same for every user).",
    privacy_title: "Video surveillance and privacy",
    privacy_intro: "This application films people and can identify them by their face. In Belgium and the EU, several rules apply depending on the use:",
    privacy_list: `<li><b>Belgian Camera Act (21 March 2007)</b>: declare every camera at
        <a href="https://www.declarationcamera.be" target="_blank" rel="noopener">declarationcamera.be</a>
        (except personal and household use inside a private home), put up the warning pictogram,
        keep a register of image processing, and do not film the public road or the neighbours.</li>
      <li><b>Retention</b>: 1 month maximum in principle, unless the footage proves an offence or damage.
        Adjustable in Settings.</li>
      <li><b>Face recognition = biometric data</b> (GDPR art. 9): prohibited in principle, except under an exception
        such as the explicit and free consent of every registered person. Do not use it to identify
        visitors, customers or passers-by.</li>
      <li><b>At work</b>: filming employees is regulated (collective agreement No. 68): prior information and a legitimate purpose.</li>
      <li><b>People filmed</b>: they have a right to access their images and can ask for them to be deleted.</li>`,
    privacy_disclaimer: `This reminder is not legal advice. If in doubt, contact the Data Protection Authority
      (<a href="https://www.dataprotectionauthority.be" target="_blank" rel="noopener">dataprotectionauthority.be</a>).`,
    privacy_check: "I have read these obligations", privacy_ok: "I understand",
  },
};

const LOCALES = { fr: "fr-BE", nl: "nl-BE", en: "en-GB" };

function detectLang() {
  try {
    const saved = localStorage.getItem("vs-lang");
    if (saved && I18N[saved]) return saved;
  } catch { /* stockage indisponible */ }
  const nav = (navigator.language || "fr").slice(0, 2).toLowerCase();
  return I18N[nav] ? nav : "fr";
}

let LANG = detectLang();
let VALUE_NAMES = {};  // clé neutre -> {fr, nl, en}, chargé depuis le serveur

// Texte de l'interface, avec paramètres : t("fps", {n: 7})
function t(key, params = {}) {
  const s = I18N[LANG][key] ?? I18N.fr[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => params[k] ?? "");
}
// Nom d'une valeur neutre (couleur, vêtement, arme) ; inconnue = affichée telle quelle
const tv = key => (key && VALUE_NAMES[key]?.[LANG]) || key;
// Libellé d'arme qui peut contenir plusieurs types : « assault_rifle, handgun »
const tlabel = label => (label || "").split(", ").map(tv).join(", ");

// Textes fixes de la page : data-i18n (texte), data-i18n-html, data-i18n-ph (placeholder), data-i18n-title
function applyStatic(root = document) {
  document.documentElement.lang = LANG;
  root.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-html]").forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  root.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
  root.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.dataset.i18nTitle); });
}
