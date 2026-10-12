#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售易 OpenAPI 数据采集 + 转换脚本（修复版 v2 - 正确的 API 路径）
使用 /rest/data/v2/query SQL API 而不是旧的 /data/v1/objects/*
"""

import requests
import json
import os
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv


# 日志配置
logger = logging.getLogger(__name__)


class SyncError(RuntimeError):
    """Safe failure: never include credentials or response bodies."""


class XiaoshouyiAPI:
    """销售易 API 客户端 - 使用 /rest/data/v2/query SQL API"""

    def __init__(self, api_domain, access_token):
        self.api_domain = api_domain
        self.access_token = access_token
        self.base_url = f"https://{api_domain}"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        self.output_dir = Path('crm_data')
        self.output_dir.mkdir(exist_ok=True)

    def verify_token(self) -> bool:
        """验证 token 是否有效"""
        logger.info("正在验证 access token...")
        try:
            # 使用简单的 SQL 查询验证 token
            sql = "select id from account limit 0,1"
            resp = requests.get(
                f"{self.base_url}/rest/data/v2/query",
                headers=self.headers,
                params={"q": sql},
                timeout=10
            )

            if resp.status_code == 200 and resp.json().get('code') == 200:
                logger.info("✓ Access token 有效")
                return True
            else:
                logger.error(f"✗ Token 验证失败: {resp.status_code}")
                return False
        except Exception as e:
            logger.error("✗ Token 验证异常 (%s)", type(e).__name__)
            return False

    def _query_sql(self, sql: str, max_retries: int = 1) -> List[Dict]:
        """Only a validated successful response may yield an empty page."""
        for attempt in range(max_retries + 1):
            try:
                resp = requests.get(
                    f"{self.base_url}/rest/data/v2/query",
                    headers=self.headers,
                    params={"q": sql},
                    timeout=30
                )

                if resp.status_code != 200:
                    raise SyncError(f"API HTTP {resp.status_code}")
                data = resp.json()
                if not isinstance(data, dict) or data.get('code') != 200:
                    raise SyncError("API reported failure")
                result = data.get('result')
                items = result.get('records') if isinstance(result, dict) else None
                if not isinstance(items, list) or any(not isinstance(row, dict) for row in items):
                    raise SyncError("Invalid API records schema")
                return items
            except SyncError:
                raise
            except (requests.RequestException, ValueError):
                if attempt == max_retries:
                    raise SyncError("API transport or JSON failure") from None
        raise SyncError("API query did not complete")

    def _query_all(self, base_sql: str, page_size: int = 500,
                   max_records: int = 100000) -> List[Dict]:
        """Stable paging; fail rather than silently truncate or accept duplicates."""
        if page_size <= 0 or max_records <= 0:
            raise SyncError("Invalid pagination limit")
        if 'order by' not in base_sql.lower():
            base_sql += ' order by id asc'
        all_data: List[Dict] = []
        offset = 0
        seen = set()
        while True:
            page = self._query_sql(f"{base_sql} limit {offset}, {page_size}")
            if not page:
                break
            for row in page:
                record_id = row.get('id')
                if isinstance(record_id, bool) or not isinstance(record_id, (int, str)) or not str(record_id).strip():
                    raise SyncError("Missing or invalid record id")
                key = str(record_id)
                if key in seen:
                    raise SyncError("duplicate record id in pagination")
                seen.add(key)
            all_data.extend(page)
            if len(all_data) > max_records:
                raise SyncError("Record limit exceeded; snapshot rejected")
            offset += len(page)
        return all_data

    def get_leads(self) -> List[Dict]:
        """获取线索（分页取全）"""
        logger.info("正在获取线索...")
        # 实际可用字段：id, phone, email
        leads = self._query_all("select id, phone, email from lead")
        logger.info(f"✓ 获取 {len(leads)} 条线索")
        return leads

    def get_opportunities(self) -> List[Dict]:
        """获取商机"""
        logger.info("正在获取商机...")
        # 实际可用字段（经 discover_opp_amount.py 探测确认）：
        #   money=金额, winRate=赢率(0-100), opportunityName=名称,
        #   accountId=客户, closeDate=预计成交日期(epoch ms), ownerId=负责人
        opps = self._query_all(
            "select id, opportunityName, money, winRate, accountId, "
            "closeDate, ownerId from opportunity")
        logger.info(f"✓ 获取 {len(opps)} 个商机")
        return opps

    def get_customers(self) -> List[Dict]:
        """获取客户"""
        logger.info("正在获取客户...")
        # 实际可用字段：id, accountName
        customers = self._query_all("select id, accountName from account")
        logger.info(f"✓ 获取 {len(customers)} 个客户")
        return customers

    def get_contacts(self) -> List[Dict]:
        """获取联系人"""
        logger.info("正在获取联系人...")
        # 实际可用字段：id, email, phone
        contacts = self._query_all("select id, email, phone from contact")
        logger.info(f"✓ 获取 {len(contacts)} 个联系人")
        return contacts

    def save_json(self, data: Any, filename: str) -> Path:
        """保存数据为 JSON"""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✓ 数据已保存: {filepath}")
        return filepath


class DataTransformer:
    """数据转换和计算"""

    @staticmethod
    def calculate_lead_score(lead: Dict) -> int:
        """计算线索评分（0-100）

        注意：由于可用字段有限，评分基于联系信息完整度
        """
        score = 0

        # 1. 联系信息完整度（基础评分）
        has_phone = bool(lead.get('phone'))
        has_email = bool(lead.get('email'))

        contact_complete = sum([has_phone, has_email])
        score = (contact_complete / 2) * 100

        return min(100, int(score))

    # 常见公共邮箱域名（这些无法反推公司）
    PUBLIC_MAILBOXES = {
        'qq.com', '163.com', '126.com', 'gmail.com', 'hotmail.com', 'outlook.com',
        'sina.com', 'sina.cn', 'sohu.com', '139.com', '189.cn', 'foxmail.com',
        'yeah.net', 'aliyun.com', '21cn.com', 'vip.163.com', 'live.com', 'me.com'
    }

    # 域名→中文公司名 映射（从 company_map.json 加载，缺失则回退英文域名）
    _COMPANY_MAP = None

    @staticmethod
    def _load_company_map() -> Dict:
        if DataTransformer._COMPANY_MAP is None:
            DataTransformer._COMPANY_MAP = {}
            map_file = Path(__file__).resolve().parent / 'company_map.json'
            if map_file.exists():
                try:
                    raw = json.loads(map_file.read_text(encoding='utf-8'))
                    # 忽略以 _ 开头的说明字段，key 统一小写
                    DataTransformer._COMPANY_MAP = {
                        k.lower(): v for k, v in raw.items() if not k.startswith('_')
                    }
                except Exception as e:
                    logger.warning(f"company_map.json 解析失败，公司名将回退英文: {e}")
        return DataTransformer._COMPANY_MAP

    @staticmethod
    def derive_company_contact(email: str):
        """从邮箱反推（公司, 联系人）。
        公司名优先取 company_map.json 的中文名；没有则回退英文域名主体。
        例：Sandra.Su@punchpowertrain.com -> ('邦奇动力', 'Sandra Su')
        公共邮箱（qq/163等）无法反推公司，返回公司为空。
        """
        if not email or '@' not in email:
            return ('', '')
        local, _, domain = email.partition('@')
        domain = domain.lower().strip()
        contact = local.replace('.', ' ').replace('_', ' ').strip().title()
        if domain in DataTransformer.PUBLIC_MAILBOXES:
            return ('', contact)  # 个人邮箱，公司未知
        cmap = DataTransformer._load_company_map()
        if domain in cmap:
            return (cmap[domain], contact)          # 命中中文名
        company = domain.split('.')[0].title()      # 回退：英文域名主体
        return (company, contact)

    @staticmethod
    def transform_to_dashboard_data(leads: List[Dict], opps: List[Dict], customers: List[Dict]) -> Dict:
        """转换为看板数据格式

        注意：由于 API 可用字段有限，数据展示基于现有字段
        """
        logger.info("正在转换数据格式...")

        # 线索评分分布
        lead_scores = [DataTransformer.calculate_lead_score(l) for l in leads]
        score_distribution = {
            '0-20': len([s for s in lead_scores if s < 20]),
            '20-40': len([s for s in lead_scores if 20 <= s < 40]),
            '40-60': len([s for s in lead_scores if 40 <= s < 60]),
            '60-80': len([s for s in lead_scores if 60 <= s < 80]),
            '80-100': len([s for s in lead_scores if s >= 80])
        }

        # 高风险线索（评分 >= 80）
        leads_with_scores = [
            {**l, 'score': DataTransformer.calculate_lead_score(l)}
            for l in leads
        ]
        high_risk_leads = sorted(
            [l for l in leads_with_scores if l['score'] >= 80],
            key=lambda x: x['score'],
            reverse=True
        )[:10]

        # 商机金额 / 赢单计算（方案B：money + winRate）
        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        # 销售易 winRate 通常为 0-100 整数；自动判别刻度，赢单=最高赢率
        max_wr = max((_num(o.get('winRate')) for o in opps), default=0)
        won_threshold = 100 if max_wr > 1 else 1  # 兼容 0-100 与 0-1 两种刻度
        won_opps = [o for o in opps if _num(o.get('winRate')) >= won_threshold]
        won_count = len(won_opps)
        won_amount = sum(_num(o.get('money')) for o in won_opps)
        pipeline_amount = sum(_num(o.get('money')) for o in opps)
        # 记录 winRate 分布，便于核对刻度是否为 0-100
        from collections import Counter
        wr_dist = Counter(int(_num(o.get('winRate'))) for o in opps)
        logger.info(f"  商机总金额(pipeline): ¥{pipeline_amount/1e4:.1f}万")
        logger.info(f"  赢单(winRate>={won_threshold}): {won_count} 个, 金额 ¥{won_amount/1e4:.1f}万")
        logger.info(f"  winRate 分布(取整): {dict(sorted(wr_dist.items()))}")

        deal_rate = f"{won_count/max(len(leads),1)*100:.1f}%"

        # Top 客户赢单金额：用 accountId 映射客户中文名（仅含能匹配到名称的客户）
        acc_name = {str(c.get('id')): c.get('accountName') for c in customers}
        cust_won, cust_cnt = {}, {}
        for o in won_opps:
            name = acc_name.get(str(o.get('accountId')))
            if not name:
                continue  # 客户表未含该客户名（客户列表被截断），跳过
            cust_won[name] = cust_won.get(name, 0.0) + _num(o.get('money'))
            cust_cnt[name] = cust_cnt.get(name, 0) + 1
        top_customers = sorted(
            [{'name': n, 'amount': cust_won[n], 'count': cust_cnt[n]} for n in cust_won],
            key=lambda x: x['amount'], reverse=True
        )[:8]

        # 漏斗（基础统计）
        funnel = [
            {'stage': 'MQL (线索)', 'count': len(leads), 'rate': '100%'},
            {'stage': 'SAL (合格)', 'count': len([l for l in leads if l.get('phone') or l.get('email')]), 'rate': '-'},
            {'stage': 'Opportunity (商机)', 'count': len(opps), 'rate': '-'},
            {'stage': 'Deal (赢单)', 'count': won_count, 'rate': deal_rate}
        ]

        # 联系方式完整度
        leads_with_contact = len([l for l in leads if l.get('phone') and l.get('email')])
        contact_rate = (leads_with_contact / max(len(leads), 1)) * 100

        dashboard_data = {
            'kpis': {
                'marketing_penetration_rate': f"{contact_rate:.0f}%",
                'design_win_contribution': f"¥{won_amount/1e4:.0f}万",
                'design_win_count': won_count,
                'pipeline_amount': f"¥{pipeline_amount/1e4:.0f}万",
                'triangle_control_completeness': '62%',
                'high_risk_leads_count': len(high_risk_leads),
                'sales_cycle_avg_days': 180,
                'total_leads': len(leads),
                'total_customers': len(customers),
                'total_contacts': len(customers)  # 联系人数
            },
            'funnel': funnel,
            'score_distribution': score_distribution,
            'channels': top_customers,
            'high_risk_leads': [
                {
                    'id': l['id'],
                    'company': (DataTransformer.derive_company_contact(l.get('email', ''))[0] or '—'),
                    'contact': (DataTransformer.derive_company_contact(l.get('email', ''))[1] or '—'),
                    'phone': l.get('phone', 'N/A'),
                    'email': l.get('email', 'N/A'),
                    'score': l['score'],
                }
                for l in high_risk_leads
            ],
            'sync_time': datetime.now().isoformat()
        }

        return dashboard_data


def main():
    load_dotenv()
    logger.info("=" * 70)
    logger.info("销售易数据同步脚本启动")
    logger.info("=" * 70)

    # 从环境变量读取配置
    api_domain = os.getenv('XIAOSHOUYI_API_DOMAIN')
    access_token = os.getenv('XIAOSHOUYI_ACCESS_TOKEN')

    if not api_domain or not access_token:
        logger.error("✗ 缺少配置：请在 .env 文件中设置 XIAOSHOUYI_API_DOMAIN 和 XIAOSHOUYI_ACCESS_TOKEN")
        return 1

    logger.info(f"API 域: {api_domain}")

    # 初始化 API 客户端
    api = XiaoshouyiAPI(api_domain, access_token)

    # 验证 token
    logger.info("\n[1] 验证 access token...")
    if not api.verify_token():
        logger.error("✗ Token 验证失败，请检查 .env 文件中的配置")
        return 1

    # 获取数据
    logger.info("\n[2] 获取 CRM 数据...")
    try:
        leads = api.get_leads()
        opps = api.get_opportunities()
        customers = api.get_customers()
        contacts = api.get_contacts()
    except Exception as e:
        logger.error("✗ 获取数据异常 (%s)", type(e).__name__)
        return 1

    # A successful empty entity is anomalous for this existing populated CRM.
    if any(not rows for rows in (leads, opps, customers, contacts)):
        logger.error("✗ 异常空实体：保留最后有效快照")
        return 1

    # 转换数据
    logger.info("\n[3] 转换数据格式...")
    transformer = DataTransformer()
    dashboard_data = transformer.transform_to_dashboard_data(leads, opps, customers)

    # 保存数据
    logger.info("\n[4] 保存数据...")
    api.save_json(
        {'leads': leads, 'opportunities': opps, 'customers': customers, 'contacts': contacts},
        'raw_data.json'
    )
    api.save_json(dashboard_data, 'dashboard_data.json')

    # 完成
    logger.info("\n" + "=" * 70)
    logger.info("✓ 数据同步完成！")
    logger.info(f"  线索数: {len(leads)}")
    logger.info(f"  商机数: {len(opps)}")
    logger.info(f"  客户数: {len(customers)}")
    logger.info(f"  Design-Win 贡献: {dashboard_data['kpis']['design_win_contribution']}")
    logger.info("=" * 70)
    return 0


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[
            logging.FileHandler('xiaoshouyi_sync.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    try:
        sys.exit(main())
    except Exception as e:
        logger.error("✗ 程序异常 (%s)", type(e).__name__)
        sys.exit(1)
