import re
with open('bot/handlers/backup.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('text = "\n".join(lines)', 'text = "\\n".join(lines)')
code = code.replace('await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))', 'await context.bot.send_message(chat_id=chat_id, text="\\n".join(lines))')
code = code.replace('await query.edit_message_text(f"{BACKUP_FULL_IN_PROGRESS}\n\n⏳', 'await query.edit_message_text(f"{BACKUP_FULL_IN_PROGRESS}\\n\\n⏳')
code = code.replace('await query.edit_message_text(f"{BACKUP_USERMAN_IN_PROGRESS}\n\n⏳', 'await query.edit_message_text(f"{BACKUP_USERMAN_IN_PROGRESS}\\n\\n⏳')

with open('bot/handlers/backup.py', 'w', encoding='utf-8') as f:
    f.write(code)
