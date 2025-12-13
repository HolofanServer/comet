"""
Module availability tests for CI.

Tests that critical modules can be imported without errors.
"""

import importlib.util


class TestModuleAvailability:
    """Test that critical modules are available."""

    def test_cog_modules_available(self):
        """Test that cog modules can be found."""
        modules = [
            'cogs.tool.omikuji',
            'cogs.manage.user_warning_system',
            'cogs.homepage.server_analyzer',
        ]

        for module_name in modules:
            spec = importlib.util.find_spec(module_name)
            assert spec is not None, f"Module {module_name} not found"

    def test_utils_modules_available(self):
        """Test that utility modules can be found."""
        modules = [
            'utils.database',
            'utils.error',
            'utils.logging',
            'utils.presence',
            'utils.startup',
        ]

        for module_name in modules:
            spec = importlib.util.find_spec(module_name)
            assert spec is not None, f"Module {module_name} not found"

    def test_rank_modules_available(self):
        """Test that rank system modules can be found."""
        modules = [
            'models.rank.level_config',
            'models.rank.level_formula',
            'models.rank.voice_activity',
            'utils.rank.voice_manager',
            'utils.rank.formula_manager',
        ]

        for module_name in modules:
            spec = importlib.util.find_spec(module_name)
            assert spec is not None, f"Module {module_name} not found"


class TestDatabaseFunctions:
    """Test database utility functions."""

    def test_database_has_required_functions(self):
        """Test that database module has required functions."""
        from utils import database

        required_functions = ['get_db_pool', 'execute_query', 'close_db_pool',
                             'get_db_config', 'get_database_url']

        for func_name in required_functions:
            assert hasattr(database, func_name), f"database module missing {func_name}"
            assert callable(getattr(database, func_name)), f"{func_name} is not callable"


class TestProjectStructure:
    """Test project structure integrity."""

    def test_required_config_files_exist(self):
        """Test that required configuration files exist."""
        import os

        required_files = [
            'config/bot.json',
            'config/version.json',
            'pytest.ini',
            'requirements.txt',
            '.env.example',
        ]

        for filepath in required_files:
            assert os.path.exists(filepath), f"Required file {filepath} does not exist"

    def test_migration_directory_valid(self):
        """Test that migrations directory exists and contains SQL files."""
        import os

        assert os.path.exists('migrations'), "migrations directory does not exist"

        sql_files = [f for f in os.listdir('migrations') if f.endswith('.sql')]
        assert len(sql_files) > 0, "No SQL migration files found"

    def test_cogs_directory_structure(self):
        """Test that cogs directory structure is valid."""
        import os

        cog_dirs = ['cogs/tool', 'cogs/manage', 'cogs/homepage',
                    'cogs/note', 'cogs/report', 'cogs/aus']

        for cog_dir in cog_dirs:
            assert os.path.exists(cog_dir), f"Cog directory {cog_dir} does not exist"
