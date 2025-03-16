# standard library
import json
from pprint import pprint
# user custom
from src.functional import parse_json_item, merge_two

bmf_json1 = {
    "children": [
        {
            "date_added": "13372929742000000",
            "date_last_used": "0",
            "guid": "a3fe0b16-048f-477b-829d-5e3c1aa9a625",
            "id": "621",
            "name": "2025 年日期和截止日期",
            "type": "url",
            "url": "https://cvpr.thecvf.com/Conferences/2025/Dates"
        },
        {
            "date_added": "13362465371000000",
            "date_last_used": "0",
            "guid": "3dd0b7ce-3687-4855-a277-b956a29be29a",
            "id": "634",
            "name": "控制台-讯飞开放平台",
            "type": "url",
            "url": "https://console.xfyun.cn/services/cbm"
        },
        {
            "children": [
                {
                    "date_added": "13310307483000000",
                    "date_last_used": "0",
                    "guid": "a7b87a99-d533-46ac-9b8d-6a72089c715a",
                    "id": "699",
                    "name": "FeiShu-StudySpace-Daily",
                    "type": "url",
                    "url": "https://yhe9zi0xdn.feishu.cn/wiki/wikcngqWIaRhRIi1j8Hx5NjphEd"
                },
                {
                    "date_added": "13298816548000000",
                    "date_last_used": "0",
                    "guid": "5a6df9b0-0caf-47ac-9aa4-dfeaf67d865d",
                    "id": "700",
                    "name": "Notion | Getting Started",
                    "type": "url",
                    "url": "https://www.notion.so/Getting-Started-8f476c2224f0445e89c0b7e08562ec4d"
                },
                {
                    "date_added": "13364036263000000",
                    "date_last_used": "0",
                    "guid": "d5dd81b0-c1ec-4909-b2df-3393ef432591",
                    "id": "701",
                    "name": "Capacities – A studio for your mind",
                    "type": "url",
                    "url": "https://capacities.io/"
                }
            ],
            "date_added": "13379779051942452",
            "date_last_used": "0",
            "date_modified": "0",
            "guid": "9178d80c-ae09-4c49-80a1-5dea46888afc",
            "id": "698",
            "name": "笔记页",
            "type": "folder"
        },
    ],
    "date_added": "13379779051939864",
    "date_last_used": "0",
    "date_modified": "0",
    "guid": "c620c100-991e-446c-88e7-77cf16dd63cb",
    "id": "620",
    "name": "会议官网",
    "type": "folder"
}
bmf_json2 = {
    "children": [
        {
            "date_added": "13362465371000000",
            "date_last_used": "0",
            "guid": "3dd0b7ce-3687-4855-a277-b956a29be29a",
            "id": "634",
            "name": "控制台-讯飞开放平台",
            "type": "url",
            "url": "https://console.xfyun.cn/services/cbm"
        },
        {
            "date_added": "13362473106000000",
            "date_last_used": "0",
            "guid": "33d12677-32b4-43fc-894f-1a387c73da10",
            "id": "635",
            "name": "DeepSeek 开放平台",
            "type": "url",
            "url": "https://platform.deepseek.com/api_keys"
        },
        {
            "children": [
                {
                "date_added": "13372929742000000",
                "date_last_used": "0",
                "guid": "a3fe0b16-048f-477b-829d-5e3c1aa9a625",
                "id": "621",
                "name": "2025 年日期和截止日期",
                "type": "url",
                "url": "https://cvpr.thecvf.com/Conferences/2025/Dates"
                }
            ],
            "date_added": "13379779051939864",
            "date_last_used": "0",
            "date_modified": "0",
            "guid": "c620c100-991e-446c-88e7-77cf16dd63cb",
            "id": "620",
            "name": "会议官网",
            "type": "folder"
        },
        {
            "date_added": "13362503865000000",
            "date_last_used": "0",
            "guid": "66c19ce2-802f-44a6-8325-b72fc423e940",
            "id": "641",
            "name": "阿里云百炼",
            "type": "url",
            "url": "https://bailian.console.aliyun.com/?spm=5176.29228872.J_TC9GqcHi2edq9zUs9ZsDQ.1.74cd38b14ybTKR#/api_key"
        },
    ],
    "date_added": "13379779051940297",
    "date_last_used": "0",
    "date_modified": "0",
    "guid": "f7150dfc-03b1-4878-8184-e4cd6e340d32",
    "id": "633",
    "name": "开发者API",
    "type": "folder"
}

# bmf_json1 = json.loads(bmf_json1)
# bmf_json2 = json.loads(bmf_json2)

bmf1 = parse_json_item(bmf_json1)
bmf2 = parse_json_item(bmf_json2)
pprint(bmf1)
pprint(bmf2)
print()

bmf = merge_two(bmf1, bmf2)
print()
pprint(bmf)
