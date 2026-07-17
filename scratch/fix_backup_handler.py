import re

with open('bot/handlers/backup.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Insert the locks dict and background functions before backup_full
background_logic = """
_BACKUP_LOCKS: dict[str, bool] = {}

def _is_backup_running(router_key: str) -> bool:
    return _BACKUP_LOCKS.get(router_key, False)

def _set_backup_running(router_key: str, state: bool):
    if state:
        _BACKUP_LOCKS[router_key] = True
    else:
        _BACKUP_LOCKS.pop(router_key, None)

async def _background_backup_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    router_key = job.data["router_key"]
    chat_id = job.data["chat_id"]
    user_id = job.data["user_id"]
    b_type = job.data["type"]
    
    try:
        if b_type == "full":
            result = await run_blocking(backup_service.full_backup, router_key)
            await run_blocking(log_action, "full_backup", "", router_key, user_id)
            await run_blocking(
                record_backup_result,
                router_key, "full", result["success"],
                result.get("message", ""), file_name=result.get("local_path", ""),
            )
            if result["success"]:
                downloaded = result.get("downloaded", [])
                lines = [f"✅ اكتمل النسخ الاحتياطي الكامل بنجاح: {result['message']}"]
                if downloaded:
                    lines.append(f"📁 تم تحميل {len(downloaded)} ملف محلياً")
                else:
                    lines.append("⚠️ الملفات لا تزال على الراوتر فقط")
                
                text = "\\n".join(lines)
                await context.bot.send_message(chat_id=chat_id, text=text)
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ فشل النسخ الاحتياطي: {result['message']}")
                
        elif b_type == "userman":
            result = await run_blocking(backup_service.userman_backup, router_key)
            await run_blocking(log_action, "userman_backup", "", router_key, user_id)
            await run_blocking(
                record_backup_result,
                router_key, "userman", result["success"],
                result.get("message", ""), file_name=result.get("filename", ""),
            )
            if result["success"]:
                filename = result.get("filename", "backup.tar")
                lines = [
                    f"✅ اكتمل النسخ الاحتياطي لـ User Manager بنجاح: {result['message']}",
                    f"👥 المستخدمين: {result['users_count']}",
                    f"📋 البروفايلات: {result['profiles_count']}",
                    f"📦 {filename}",
                ]
                await context.bot.send_message(chat_id=chat_id, text="\\n".join(lines))
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ فشل النسخ لـ User Manager: {result['message']}")
    except Exception as e:
        logger.error(f"Background backup failed for {router_key}: {e}")
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ حدث خطأ غير متوقع أثناء النسخ الاحتياطي في الخلفية للراوتر {router_key}.")
        except Exception:
            pass
    finally:
        _set_backup_running(router_key, False)

@require_role("operator")
@admin_only
async def backup_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is not None and is_duplicate_callback(query.data, update.effective_user.id):
        return
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]
    
    if _is_backup_running(router_key):
        await query.edit_message_text("⚠️ توجد عملية نسخ احتياطي جارية حالياً لهذا الراوتر. الرجاء الانتظار حتى تكتمل.", reply_markup=get_backup_keyboard())
        return
        
    await query.edit_message_text(f"{BACKUP_FULL_IN_PROGRESS}\\n\\n⏳ يتم تشغيل المهمة في الخلفية، سيصلك إشعار عند الانتهاء.", reply_markup=get_backup_keyboard())
    
    _set_backup_running(router_key, True)
    context.job_queue.run_once(
        _background_backup_job,
        when=1,
        data={
            "router_key": router_key,
            "user_id": update.effective_user.id,
            "chat_id": update.effective_chat.id,
            "type": "full"
        }
    )

@require_role("operator")
@admin_only
async def backup_userman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]
    
    if _is_backup_running(router_key):
        await query.edit_message_text("⚠️ توجد عملية نسخ احتياطي جارية حالياً لهذا الراوتر. الرجاء الانتظار حتى تكتمل.", reply_markup=get_backup_keyboard())
        return
        
    await query.edit_message_text(f"{BACKUP_USERMAN_IN_PROGRESS}\\n\\n⏳ يتم تشغيل المهمة في الخلفية، سيصلك إشعار عند الانتهاء.", reply_markup=get_backup_keyboard())
    
    _set_backup_running(router_key, True)
    context.job_queue.run_once(
        _background_backup_job,
        when=1,
        data={
            "router_key": router_key,
            "user_id": update.effective_user.id,
            "chat_id": update.effective_chat.id,
            "type": "userman"
        }
    )
"""

# We need to replace the definitions of backup_full and backup_userman
pattern = r'@require_role\("operator"\)\n@admin_only\nasync def backup_full[\s\S]*?async def backup_userman[\s\S]*?reply_markup=get_backup_keyboard\(\),\n        \)'
code = re.sub(pattern, background_logic.strip(), code)

with open('bot/handlers/backup.py', 'w', encoding='utf-8') as f:
    f.write(code)
