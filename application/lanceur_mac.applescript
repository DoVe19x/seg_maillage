-- Lanceur macOS de « Seg-Maillage » (compilé en .app par creer_app_mac.sh).
-- Démarre application/lancer_mac.sh en arrière-plan : ce script choisit l'environnement Python,
-- lance le serveur local, qui ouvre lui-même la fenêtre de l'application.
on run
	set appPath to POSIX path of (path to me)
	set dossier to do shell script "dirname " & quoted form of appPath
	set lanceur to dossier & "/application/lancer_mac.sh"
	try
		do shell script "test -f " & quoted form of lanceur
	on error
		display alert "Seg-Maillage" message "Dossier « application » introuvable : l'application doit rester dans le dossier seg_maillage." as critical
		return
	end try
	do shell script "nohup /bin/bash " & quoted form of lanceur & " > /dev/null 2>&1 &"
end run
