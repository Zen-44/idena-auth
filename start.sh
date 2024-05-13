# script to get the bot up and running

pkill gunicorn
screen -X -S bot quit
screen -X -S site quit

cd idena-auth
screen -dmS bot python3.11 bot.py

# Start the site

# gunicorn manages the ssl cert
# screen -dmS site gunicorn -b :443 --certfile=[CERT_PATH] --keyfile=[CERT_KEY_PATH] auth:app

# nginx manages the ssl cert
# screen -dmS site gunicorn -b :PORT auth:app

cd

# crontab for reboots
# (crontab -l 2>/dev/null; echo "@reboot bash $PWD/idena-auth/start.sh") | crontab -
# magic symbol remover
# sed -i 's/\r$//' idena-auth/start.sh
