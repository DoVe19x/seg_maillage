@echo off
rem ===========================================================================
rem  Seg-Maillage - lanceur Windows (double-clic)
rem  Segmentation osseuse CT et maillage des os en STL (etapes 1 a 5 de CT-CORA3D).
rem  Python : 1) l'environnement propre a cet ordinateur, %LOCALAPPDATA%\SegMaillage\venv (hors OneDrive,
rem              rapide), s'il existe et contient les bibliotheques ;
rem           2) sinon PMD2\.venv s'il a ete cree sous Windows et contient les bibliotheques ;
rem           3) sinon l'environnement propre a cet ordinateur est cree (premier lancement).
rem  Fenetre : native (application\fenetre.py, bibliotheque pywebview installee une fois dans
rem            %LOCALAPPDATA%\SegMaillage) ; si c'est impossible, Edge ou Chrome comme avant.
rem  Le serveur tourne sans console (pythonw) ; journal : %LOCALAPPDATA%\SegMaillage\SegMaillage.log
rem  Fermer la fenetre de l'application suffit : le serveur s'arrete seul.
rem ===========================================================================
setlocal
set "ICI=%~dp0"
set "APP=%ICI%application\serveur.py"
set "REQ=%ICI%application\requirements.txt"
set "LOCAL=%LOCALAPPDATA%\SegMaillage\venv"
rem verification rapide : les bibliotheques sont-elles installees ? (presence seulement, sans les charger : 0,02 s
rem au lieu de plusieurs secondes ; le serveur les importe juste apres)
set "MODULES=import importlib.util as u, sys; sys.exit(any(u.find_spec(m) is None for m in 'numpy scipy pydicom SimpleITK vtk trimesh pyvista matplotlib PIL'.split()))"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if exist "%APP%" goto chercher
echo Fichier introuvable : "%APP%"
echo Ce lanceur doit rester dans le dossier seg_maillage.
pause
exit /b 1

:chercher
set "PY=%LOCAL%\Scripts\python.exe"
if exist "%PY%" "%PY%" -c "%MODULES%" >nul 2>nul && goto lancer
set "PY=%ICI%..\.venv\Scripts\python.exe"
if exist "%PY%" "%PY%" -c "%MODULES%" >nul 2>nul && goto lancer
set "PY=%LOCAL%\Scripts\python.exe"

echo Premier lancement : installation de l'environnement Python, quelques minutes...
set "BASE="
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>nul && set "BASE=py -3"
if not defined BASE python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>nul && set "BASE=python"
if defined BASE goto installer
echo Python 3.10 ou plus recent est introuvable.
echo Installez-le depuis https://www.python.org/downloads/
echo en cochant "Add python.exe to PATH", puis relancez ce fichier.
pause
exit /b 1

:installer
%BASE% -m venv "%LOCAL%"
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%REQ%"
"%PY%" -c "%MODULES%" >nul 2>nul && goto lancer
echo L'installation des bibliotheques a echoue : verifiez la connexion internet.
pause
exit /b 1

:lancer
"%PY%" "%ICI%application\fenetre.py" --verifier >nul 2>nul && goto demarrer
echo Premier lancement : installation de la fenetre de l'application...
"%PY%" "%ICI%application\fenetre.py" --installer

:demarrer
rem pythonw.exe = le meme Python, sans console : seule la fenetre de l'application apparait
set "PYW=%PY:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PY%"
if not exist "%LOCALAPPDATA%\SegMaillage" mkdir "%LOCALAPPDATA%\SegMaillage"
start "Seg-Maillage" /b "%PYW%" "%APP%" >> "%LOCALAPPDATA%\SegMaillage\SegMaillage.log" 2>&1
exit /b 0
