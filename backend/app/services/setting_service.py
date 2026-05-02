import json
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import SystemSetting


class SettingService:
    """系统设置服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_all_settings(self) -> Dict[str, Any]:
        """获取所有设置"""
        settings = self.db.query(SystemSetting).all()
        result = {}
        for setting in settings:
            result[setting.setting_key] = self._parse_value(setting)
        return result
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取单个设置"""
        setting = self.db.query(SystemSetting).filter(
            SystemSetting.setting_key == key
        ).first()
        if setting:
            return self._parse_value(setting)
        return default
    
    def set_setting(self, key: str, value: Any, setting_type: str = None, description: str = None) -> SystemSetting:
        """设置单个值"""
        setting = self.db.query(SystemSetting).filter(
            SystemSetting.setting_key == key
        ).first()
        
        if setting_type is None:
            setting_type = self._get_type(value)
        
        stored_value = self._serialize_value(value)
        
        if setting:
            setting.setting_value = stored_value
            setting.setting_type = setting_type
            if description:
                setting.description = description
            setting.updated_at = datetime.now()
        else:
            setting = SystemSetting(
                setting_key=key,
                setting_value=stored_value,
                setting_type=setting_type,
                description=description
            )
            self.db.add(setting)
        
        self.db.commit()
        self.db.refresh(setting)
        return setting
    
    def set_settings(self, settings_dict: Dict[str, Any]) -> List[SystemSetting]:
        """批量设置"""
        result = []
        for key, value in settings_dict.items():
            setting = self.set_setting(key, value)
            result.append(setting)
        return result
    
    def delete_setting(self, key: str) -> bool:
        """删除设置"""
        setting = self.db.query(SystemSetting).filter(
            SystemSetting.setting_key == key
        ).first()
        if setting:
            self.db.delete(setting)
            self.db.commit()
            return True
        return False
    
    def initialize_default_settings(self):
        """初始化默认设置"""
        default_settings = {
            'system_name': ('数据仪表盘', 'string', '系统名称'),
            'language': ('zh-CN', 'string', '显示语言'),
            'theme': ('light', 'string', '主题模式'),
            'default_date_range': ('month', 'string', '默认时间范围'),
            'auto_refresh': (False, 'boolean', '自动刷新'),
            'refresh_interval': (10, 'number', '刷新间隔（分钟）'),
            'gmv_drop_threshold': (20, 'number', 'GMV下降阈值（%）'),
            'min_gmv_amount': (10000, 'number', '最低GMV金额'),
            'min_conversion_rate': (2, 'number', '最低转化率（%）'),
            'min_roi': (1.5, 'number', '最低ROI'),
            'refund_rate_threshold': (15, 'number', '退款率阈值（%）'),
            'popup_notifications': (True, 'boolean', '弹窗通知'),
            'browser_notifications': (True, 'boolean', '浏览器通知'),
            'email_alerts': (False, 'boolean', '告警邮件'),
            'email_recipient': ('', 'string', '收件邮箱'),
            'alert_frequency': ('real-time', 'string', '告警频率'),
            'export_format': ('csv', 'string', '默认导出格式'),
            'export_date_format': ('YYYY-MM-DD', 'string', '导出日期格式'),
            'export_encoding': ('utf-8', 'string', '导出编码'),
            'export_with_charts': (False, 'boolean', '包含图表')
        }
        
        for key, (value, setting_type, description) in default_settings.items():
            existing = self.db.query(SystemSetting).filter(
                SystemSetting.setting_key == key
            ).first()
            if not existing:
                setting = SystemSetting(
                    setting_key=key,
                    setting_value=self._serialize_value(value),
                    setting_type=setting_type,
                    description=description
                )
                self.db.add(setting)
        
        self.db.commit()
    
    def _parse_value(self, setting: SystemSetting) -> Any:
        """解析存储的值"""
        value = setting.setting_value
        if setting.setting_type == 'json':
            try:
                return json.loads(value) if value else None
            except:
                return None
        elif setting.setting_type == 'number':
            try:
                if '.' in value:
                    return float(value)
                return int(value)
            except:
                return 0
        elif setting.setting_type == 'boolean':
            return value.lower() in ('true', '1', 'yes', 'on')
        return value
    
    def _serialize_value(self, value: Any) -> str:
        """序列化值为存储格式"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value)
    
    def _get_type(self, value: Any) -> str:
        """获取值的类型"""
        if isinstance(value, (dict, list)):
            return 'json'
        elif isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, (int, float)):
            return 'number'
        return 'string'
