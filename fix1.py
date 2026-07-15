import pathlib

# Fix states.py
p = pathlib.Path(r'D:\New Projects 21-5\Mikrotik admin bot telegram\mikrotik_bot\bot\handlers\states.py')
text = p.read_text(encoding='utf-8')
text = text.replace('    # Hotspot card MAC binding step (44)\n    HOTSPOT_CARD_MAC = 44\n\n', '')
p.write_text(text, encoding='utf-8')
print('states.py fixed')

# Fix constants.py
p = pathlib.Path(r'D:\New Projects 21-5\Mikrotik admin bot telegram\mikrotik_bot\bot\handlers\constants.py')
text = p.read_text(encoding='utf-8')
text = text.replace('# Hotspot card MAC binding step\nWAITING_HOTSPOT_CARD_MAC = WaitingState.HOTSPOT_CARD_MAC.value\n\n', '')
p.write_text(text, encoding='utf-8')
print('constants.py fixed')

# Fix callback_constants.py
p = pathlib.Path(r'D:\New Projects 21-5\Mikrotik admin bot telegram\mikrotik_bot\bot\handlers\callback_constants.py')
text = p.read_text(encoding='utf-8')
text = text.replace('    "hs_card_bind": "hs_card_bind",\n    "hs_card_no_bind": "hs_card_no_bind",\n', '')
text = text.replace('    "hs_card_mac_choice": r"^(hs_card_bind|hs_card_no_bind)$",\n', '')
p.write_text(text, encoding='utf-8')
print('callback_constants.py fixed')
