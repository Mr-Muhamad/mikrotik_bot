import re

with open('tests/integration/test_backup_flow.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace test_backup_full_handler_success
new_full = """    @pytest.mark.asyncio
    async def test_backup_full_handler_success(self, mock_mikrotik_api, temp_backup_dir):
        from bot.handlers.backup import backup_full
        from database.models import save_user_session
        from tests.fixtures.telegram_mocks import make_mock_update
        from utils import admin_decorator
    
        admin_decorator._rate_limit_data.clear()
        save_user_session(724730774, ROUTER_KEY)
        try:
            update = make_mock_update(callback_data="backup_full")
            context = self._make_context()
            context.user_data["router_key"] = ROUTER_KEY
            mock_mikrotik_api.commands_executed.clear()
    
            with patch("core.backup_service.BACKUP_DIR", temp_backup_dir), \\
                 patch("bot.handlers.backup.log_action"):
                await backup_full(update, context)
                
                # Extract and run job
                job_func = context.job_queue.run_once.call_args[0][0]
                job_mock = MagicMock()
                job_mock.data = context.job_queue.run_once.call_args.kwargs.get("data")
                job_ctx = MagicMock()
                job_ctx.job = job_mock
                job_ctx.bot.send_message = AsyncMock()
                await job_func(job_ctx)
    
            assert any(
                c[1] in ("system/backup/save", "export")
                for c in mock_mikrotik_api.commands_executed
            )
        finally:
            admin_decorator._rate_limit_data.clear()
"""
code = re.sub(r'    @pytest\.mark\.asyncio\n    async def test_backup_full_handler_success.*?finally:\n            admin_decorator\._rate_limit_data\.clear\(\)\n', new_full, code, flags=re.DOTALL)

with open('tests/integration/test_backup_flow.py', 'w', encoding='utf-8') as f:
    f.write(code)
