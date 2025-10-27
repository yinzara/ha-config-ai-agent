"""
Configuration Manager

Handles all configuration file operations with:
- ruamel.yaml for comment preservation
- Atomic file writes
- Automatic backups with rotation
- Home Assistant validation
- Rollback on failure
"""
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Base exception for configuration errors."""
    pass


class ValidationError(ConfigurationError):
    """Raised when configuration validation fails."""
    pass


class ConfigurationManager:
    """
    Manages Home Assistant configuration files with safety features.

    Features:
    - Comment-preserving YAML operations
    - Atomic file writes (write to temp, then move)
    - Automatic backups before changes
    - Backup rotation (keeps max_backups most recent)
    - Home Assistant validation integration
    - Automatic rollback on validation failure
    - Path traversal protection
    """

    def __init__(
        self,
        config_dir: str,
        backup_dir: str,
        max_backups: int = 10,
        ha_check_config_cmd: str = "ha core check"
    ):
        """
        Initialize ConfigurationManager.

        Args:
            config_dir: Path to Home Assistant config directory
            backup_dir: Path to backup directory
            max_backups: Maximum number of backups to keep per file
            ha_check_config_cmd: Command to run HA config validation
        """
        self.config_dir = Path(config_dir).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.max_backups = max_backups
        self.ha_check_config_cmd = ha_check_config_cmd

        # Initialize ruamel.yaml with comment preservation
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self.yaml.indent(mapping=2, sequence=2, offset=2)

        # Ensure directories exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ConfigurationManager initialized:")
        logger.info(f"  Config dir: {self.config_dir}")
        logger.info(f"  Backup dir: {self.backup_dir}")
        logger.info(f"  Max backups: {self.max_backups}")

    def _validate_path(self, file_path: str) -> Path:
        """
        Validate and resolve file path to prevent path traversal.

        Args:
            file_path: Relative path to config file

        Returns:
            Resolved absolute Path object

        Raises:
            ConfigurationError: If path is invalid or outside config_dir
        """
        # Resolve relative path against config_dir
        full_path = (self.config_dir / file_path).resolve()

        # Ensure path is within config_dir (prevents path traversal)
        if not str(full_path).startswith(str(self.config_dir)):
            raise ConfigurationError(
                f"Invalid path: {file_path} is outside config directory"
            )

        return full_path

    async def read_file_raw(self, file_path: str) -> str:
        """
        Read a configuration file as raw text without parsing.

        Args:
            file_path: Relative path to config file (e.g., "configuration.yaml")

        Returns:
            Raw file content as string

        Raises:
            ConfigurationError: If file cannot be read
        """
        full_path = self._validate_path(file_path)

        if not full_path.exists():
            raise ConfigurationError(f"File not found: {file_path}")

        try:
            logger.debug(f"Reading raw config file: {file_path}")
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise ConfigurationError(f"Error reading {file_path}: {str(e)}")

    def _create_backup(self, file_path: Path) -> Path:
        """
        Create a timestamped backup of a file.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to created backup file
        """
        if not file_path.exists():
            raise ConfigurationError(f"Cannot backup non-existent file: {file_path}")

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}.backup"
        backup_path = self.backup_dir / backup_name

        # Copy file to backup
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup: {backup_path.name}")

        return backup_path

    def _rotate_backups(self, file_stem: str):
        """
        Remove old backups, keeping only max_backups most recent.

        Args:
            file_stem: Stem of the original file (e.g., "configuration")
        """
        # Find all backups for this file
        pattern = f"{file_stem}_*.backup"
        backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True  # Newest first
        )

        # Remove old backups
        for backup in backups[self.max_backups:]:
            backup.unlink()
            logger.info(f"Removed old backup: {backup.name}")

    async def write_file_raw(
        self,
        file_path: str,
        content: str,
        validate: bool = True,
        create_backup: bool = True
    ) -> None:
        """
        Write raw content to a configuration file without YAML parsing.

        This is useful for writing files that need exact formatting preserved,
        or for writing non-YAML files (like JSON for virtual device/entity files).

        Process:
        1. Validate path
        2. Create backup if file exists
        3. Write to temporary file
        4. Validate configuration if requested
        5. Atomically move temp file to target
        6. Rotate old backups
        7. Rollback on any failure

        Args:
            file_path: Relative path to config file
            content: Raw string content to write
            validate: Whether to run HA validation after write
            create_backup: Whether to backup existing file

        Raises:
            ConfigurationError: If write or validation fails
            ValidationError: If HA validation fails (will auto-rollback)
        """
        # Handle virtual files (devices, entities, areas)
        if file_path.startswith("devices/"):
            await self._write_device_json(file_path, content)
            return
        elif file_path.startswith("entities/"):
            await self._write_entity_json(file_path, content)
            return
        elif file_path.startswith("areas/"):
            await self._write_area_json(file_path, content)
            return
        elif file_path == "lovelace.yaml":
            await self._write_lovelace_yaml(content)
            return

        # Regular file handling
        full_path = self._validate_path(file_path)
        backup_path = None
        temp_path = full_path.with_suffix(f"{full_path.suffix}.tmp")

        try:
            # Step 1: Create backup if file exists
            if create_backup and full_path.exists():
                backup_path = self._create_backup(full_path)

            # Step 2: Write to temporary file
            logger.info(f"Writing raw config file: {file_path}")
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Step 3: Validate configuration if requested
            if validate:
                # Move temp to target for validation
                shutil.move(str(temp_path), str(full_path))

                # Run HA validation
                await self._validate_config()
            else:
                # Just move without validation
                shutil.move(str(temp_path), str(full_path))

            # Step 4: Rotate old backups
            if create_backup:
                self._rotate_backups(full_path.stem)

            logger.info(f"Successfully wrote raw file: {file_path}")

        except ValidationError:
            # Rollback on validation failure
            logger.error(f"Validation failed, rolling back {file_path}")
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, full_path)
                logger.info(f"Restored from backup: {backup_path.name}")
            raise

        except Exception as e:
            # Cleanup temp file on any error
            if temp_path.exists():
                temp_path.unlink()

            # Rollback on write failure
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, full_path)
                logger.info(f"Restored from backup after error: {backup_path.name}")

            raise ConfigurationError(f"Error writing raw file {file_path}: {str(e)}")

    async def _write_device_json(self, file_path: str, json_content: str):
        """Write device changes via WebSocket API."""
        from ..ha.ha_websocket import HomeAssistantWebSocket
        import json

        device_id = file_path.replace("devices/", "").replace(".json", "")
        device = json.loads(json_content)

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            raise ConfigurationError("SUPERVISOR_TOKEN not available")

        ws_url = "ws://supervisor/core/websocket"
        ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)

        try:
            await ws_client.connect()
            await ws_client.update_device(
                device_id=device_id,
                name_by_user=device.get('name_by_user'),
                area_id=device.get('area_id'),
                labels=device.get('labels', []),
                disabled_by=device.get('disabled_by')
            )
            logger.info(f"Updated device via WebSocket: {device_id}")
        finally:
            await ws_client.close()

    async def _write_entity_json(self, file_path: str, json_content: str):
        """Write entity changes via WebSocket API."""
        from ..ha.ha_websocket import HomeAssistantWebSocket
        import json

        entity_id = file_path.replace("entities/", "").replace(".json", "")
        entity = json.loads(json_content)

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            raise ConfigurationError("SUPERVISOR_TOKEN not available")

        ws_url = "ws://supervisor/core/websocket"
        ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)

        try:
            await ws_client.connect()
            await ws_client.update_entity(
                entity_id=entity_id,
                name=entity.get('name'),
                icon=entity.get('icon'),
                area_id=entity.get('area_id'),
                labels=entity.get('labels', [])
            )
            logger.info(f"Updated entity via WebSocket: {entity_id}")
        finally:
            await ws_client.close()

    async def _write_area_json(self, file_path: str, json_content: str):
        """Write area changes via WebSocket API. Creates area if it doesn't exist."""
        from ..ha.ha_websocket import HomeAssistantWebSocket
        import json

        area_id = file_path.replace("areas/", "").replace(".json", "")
        area = json.loads(json_content)

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            raise ConfigurationError("SUPERVISOR_TOKEN not available")

        ws_url = "ws://supervisor/core/websocket"
        ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)

        try:
            await ws_client.connect()

            # Check if area exists
            areas = await ws_client.list_areas()
            area_exists = any(a.get('area_id') == area_id for a in areas)

            if area_exists:
                # Update existing area
                await ws_client.update_area(
                    area_id=area_id,
                    name=area.get('name'),
                    picture=area.get('picture'),
                    icon=area.get('icon'),
                    aliases=area.get('aliases', [])
                )
                logger.info(f"Updated area via WebSocket: {area_id}")
            else:
                # Create new area - name is required
                if not area.get('name'):
                    raise ConfigurationError(f"Cannot create area {area_id}: 'name' is required")

                await ws_client.create_area(
                    name=area.get('name'),
                    picture=area.get('picture'),
                    icon=area.get('icon'),
                    aliases=area.get('aliases', [])
                )
                logger.info(f"Created new area via WebSocket: {area.get('name')}")
        finally:
            await ws_client.close()

    async def _write_lovelace_yaml(self, yaml_content: str):
        """Write lovelace config via WebSocket API."""
        from ..ha.ha_websocket import HomeAssistantWebSocket

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            raise ConfigurationError("SUPERVISOR_TOKEN not available")

        ws_url = "ws://supervisor/core/websocket"
        ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)

        try:
            await ws_client.connect()
            # Parse YAML to get the config structure
            config = self.yaml.load(yaml_content)
            await ws_client.save_lovelace_config(config)
            logger.info("Updated Lovelace config via WebSocket")
        finally:
            await ws_client.close()

    async def _validate_config(self) -> None:
        """
        Run Home Assistant configuration validation using RESTful API.

        Raises:
            ValidationError: If validation fails
        """
        logger.info("Running Home Assistant configuration validation via API...")

        try:
            import aiohttp

            supervisor_token = os.getenv('SUPERVISOR_TOKEN')
            if not supervisor_token:
                logger.warning("SUPERVISOR_TOKEN not available, skipping validation")
                return

            # Use supervisor API to validate config
            url = "http://supervisor/core/api/config/core/check_config"
            headers = {
                "Authorization": f"Bearer {supervisor_token}",
                "Content-Type": "application/json"
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()

                        # Check if validation passed
                        if result.get('result') == 'valid':
                            logger.info("Configuration validation passed ✓")
                            return
                        else:
                            # Validation failed - extract error details
                            errors = result.get('errors', 'Unknown validation error')
                            raise ValidationError(
                                f"Home Assistant configuration validation failed:\n{errors}"
                            )
                    else:
                        error_text = await response.text()
                        logger.error(f"Validation API returned status {response.status}: {error_text}")
                        raise ValidationError(
                            f"Configuration validation failed (HTTP {response.status})"
                        )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            raise ValidationError(f"Validation failed: {str(e)}")

    def list_backups(self, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available backups.

        Args:
            file_path: Optional filter for specific file's backups

        Returns:
            List of backup info dictionaries with keys:
                - name: Backup filename
                - original_file: Original file name
                - timestamp: Backup creation time
                - size: File size in bytes
        """
        if file_path:
            full_path = self._validate_path(file_path)
            pattern = f"{full_path.stem}_*.backup"
        else:
            pattern = "*.backup"

        backups = []
        for backup in sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            stat = backup.stat()

            # Parse original filename from backup name
            # Format: {stem}_{timestamp}.{ext}.backup
            parts = backup.stem.rsplit('_', 1)
            original_name = parts[0] if len(parts) > 1 else backup.stem

            backups.append({
                "name": backup.name,
                "original_file": original_name,
                "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size
            })

        return backups

    async def restore_backup(
        self,
        backup_name: str,
        validate: bool = True
    ) -> None:
        """
        Restore a configuration file from a backup.

        Args:
            backup_name: Name of backup file to restore
            validate: Whether to validate after restore

        Raises:
            ConfigurationError: If backup not found or restore fails
        """
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            raise ConfigurationError(f"Backup not found: {backup_name}")

        # Parse original filename from backup
        # Format: {stem}_{timestamp}.{ext}.backup
        parts = backup_path.stem.rsplit('_', 1)
        if len(parts) < 2:
            raise ConfigurationError(f"Invalid backup name format: {backup_name}")

        original_stem = parts[0]
        # Get extension from before .backup
        ext = backup_path.suffixes[-2] if len(backup_path.suffixes) > 1 else '.yaml'
        original_name = f"{original_stem}{ext}"

        original_path = self.config_dir / original_name

        logger.info(f"Restoring {original_name} from {backup_name}")

        # Create backup of current file before restore
        temp_backup = None
        if original_path.exists():
            temp_backup = self._create_backup(original_path)

        try:
            # Copy backup to original location
            shutil.copy2(backup_path, original_path)

            # Validate if requested
            if validate:
                await self._validate_config()

            logger.info(f"Successfully restored: {original_name}")

        except ValidationError:
            # Rollback restore on validation failure
            if temp_backup and temp_backup.exists():
                shutil.copy2(temp_backup, original_path)
                logger.info("Restore rolled back due to validation failure")
            raise
        except Exception as e:
            # Rollback on any error
            if temp_backup and temp_backup.exists():
                shutil.copy2(temp_backup, original_path)
            raise ConfigurationError(f"Error restoring backup: {str(e)}")
