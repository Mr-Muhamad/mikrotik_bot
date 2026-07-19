import re

with open('tests/bot/handlers/test_backup_handler.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_classes = """class TestBackupFull:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": True, "message": "Backup complete", "local_path": "/tmp/backup.backup"}

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \\
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_full(update, ctx)
        
        ctx.job_queue.run_once.assert_called_once()
        
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()
        
        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)):
            await job_func(job_ctx)
        
        job_ctx.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": False, "message": "Disk full", "local_path": ""}

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \\
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_full(update, ctx)
            
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()
        
        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)):
            await job_func(job_ctx)
            
        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "❌" in text
        assert "Disk full" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        await backup_module.backup_full(update, ctx)
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()
        
        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(side_effect=Exception("net down"))):
            await job_func(job_ctx)
            
        job_ctx.bot.send_message.assert_called_once()
        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "❌" in text


class TestBackupUserman:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {
            "success": True, "message": "UserMan backup complete",
            "local_path": "/tmp/um.umb", "users_count": 50, "profiles_count": 5
        }

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \\
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_userman(update, ctx)
            
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()
        
        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)):
            await job_func(job_ctx)
            
        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "50" in text
        assert "5" in text

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()
        result = {"success": False, "message": "Auth failed", "local_path": ""}

        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)), \\
             patch("bot.handlers.backup.log_action"):
            await backup_module.backup_userman(update, ctx)
            
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()
        
        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(return_value=result)):
            await job_func(job_ctx)
            
        text = job_ctx.bot.send_message.call_args.kwargs.get("text", "")
        assert "❌" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        ctx = MagicMock()
        ctx.user_data = {"router_key": "discovered_1"}
        update = _query_update()

        await backup_module.backup_userman(update, ctx)
        
        job_func = ctx.job_queue.run_once.call_args[0][0]
        job_mock = MagicMock()
        job_mock.data = ctx.job_queue.run_once.call_args.kwargs.get("data")
        job_ctx = MagicMock()
        job_ctx.job = job_mock
        job_ctx.bot.send_message = AsyncMock()
        
        with patch("bot.handlers.backup.run_blocking", new=AsyncMock(side_effect=Exception("timeout"))):
            await job_func(job_ctx)
            
        job_ctx.bot.send_message.assert_called_once()
"""

# Now replace everything from "class TestBackupFull:" to "class TestScheduleMenu:"
start_idx = code.find("class TestBackupFull:")
end_idx = code.find("class TestScheduleMenu:")
code = code[:start_idx] + new_classes + "\n\n" + code[end_idx:]

with open('tests/bot/handlers/test_backup_handler.py', 'w', encoding='utf-8') as f:
    f.write(code)
