sudo systemctl stop ddns.service
sudo systemctl disable ddns.service
sudo rm /etc/systemd/system/ddns.service
sudo systemctl daemon-reload