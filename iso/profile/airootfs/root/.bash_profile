# Modular Linux netinstall: start the text menu on the first console.
# getty@tty1 autologins as root (see getty@tty1.service.d); this profile
# launches the menu exactly once per boot on the interactive console and
# drops back to a shell when it exits.
if [ -t 0 ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ] \
   && [ -n "$TERM" ] && [ "$TERM" != "dumb" ] \
   && [ -z "$MODULAR_MENU_DONE" ]; then
  MODULAR_MENU_DONE=1
  export MODULAR_MENU_DONE
  python3 /opt/modular/installer/menu/text_menu.py
fi
