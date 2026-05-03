import os
import json
import random
import asyncio
import aiohttp
import argparse
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

# ============================================================
# 🔧 基础配置
# ============================================================
load_dotenv()
# 如果没有 .env 文件，请在此处直接填写 API_KEY
API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")
if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
    raise ValueError("❌ 未找到 API_KEY，请检查环境变量、.env 文件或直接在代码中修改")

CONFIG = {
    "api_key":  API_KEY,
    "api_base": "https://api.minimaxi.com/anthropic", # 适配 MiniMax 接口
    "model":    "MiniMax-M2.7", # 保持你的模型配置
    "concurrency": 5, # 并发数
    "output_dir":  "oriental_herbal_prompts", # 输出文件夹
}

# ============================================================
# 🌿 素材库：本草纲目 (Subjects) 
# ============================================================
# 精选的100+最具视觉特征的《本草》植物，分为核心主体和环境植物以增加组合度

# 适合作为画面的绝对主体
PLANTS_CORE = [
    "人参", "灵芝", "曼陀罗", "附子", "天门冬", "石斛", "黄连", "当归", "芍药", "牡丹", 
    "贝母", "半夏", "忍冬", "绞股蓝", "苍耳", "青蒿", "白芷", "石蒜 (彼岸花)", "合欢", "女贞", 
    "茯苓", "琥珀", "竹茹", "雷丸", "瑞香", "丁香", "藿香", "兰草", "马鞭草", "益母草",
    "祝余", "迷毂", "琅玕", "不死草", "帝屋", "三珠树", "箨草", "荀草", "瑶草", "沙棠"
]

# 适合作为背景、缠绕物或伴生物
PLANTS_ENV = [
    "银杏叶", "樟木根", "桂树枝", "松脂", "柏叶", "桑叶", "栀子花", "枫香", "沉香", "檀香", 
    "槐花", "柳华", "梧桐叶", "葛藤", "威灵仙藤", "青苔", "浮萍", "泽泻", "水芹", "芡实", 
    "枸杞子", "覆盆子", "莲蓬", "萱草", "凌霄花", "凤仙花", "牵牛花", "蔷薇", "玫瑰", "薄荷"
]

# ============================================================
# 🏔️ 素材库：山海经 (Locations)
# ============================================================
LOCATIONS = [
    "昆仑山巅 (Mount Kunlun)", "归墟深渊 (Gui Xu)", "青丘之泽 (Qingqiu)", "扶桑神树下 (Fusang)", 
    "渭水之滨 (Weishui)", "不周山遗迹 (Mount Buzhou)", "北海鳌背 (North Sea)", "雷泽 (Thunder Marsh)",
    "钟山之穴 (Mount Zhong)", "丹穴之山 (Mount Danxue)", "西王母瑶池 (Jade Terrace)", "弱水河畔 (Ruo Shui)",
    "天台云海", "沃之野", "招摇之山", "羽山荒原", "流波山雷域"
]

# ============================================================
# 🎨 素材库：风格 (Styles) - 锁定四种
# ============================================================
# 脚本只会从中抽取这四种风格，彻底摒弃皮克斯、3D等风格
STYLES = [
    "中国传统水墨画 (Traditional Chinese Ink-wash Painting, master strokes, minimalist)",
    "日本版画/浮世绘 (Japanese Woodblock Print, Ukiyo-e, flat colors, strong lines)",
    "意大利古典插画 (Classical Italian Illustration, intricate detail, tempera style)",
    "中国古风/仙侠插画 (Ancient Chinese Xianxia Illustration, ethereal atmosphere, divine aesthetic)"
]

# 植物的呈现组合方式，增加 Prompt 的多样性
COMPOSITIONS = [
    "单一主体特写 (Extreme Close-up, focus on intricate textures)",
    "共生 (Symbiosis: The core plant growing together with the environment plant)",
    "缠绕 (Entwinement: The vines of one plant wrapping around the other)",
    "寄生 (Parasitism: The core plant blooming from the bark/root of the environment plant)",
    "拟人化呈现 (Anthropomorphic representation, subtle figure form)",
    "多重组合 (Multiple combinations: A scene featuring both distinct plants)",
    "倒影与实体 (The entity of one plant and the reflection of the other in divine water)",
    "微观世界 (Micro-world perspective, looking up from the soil)"
]

# 动作与异象
ACTIONS = [
    "释放出古老的治愈荧光", "吸收日月精华脉动", "幻化为灵体鸟兽飞翔", "守护着一张发光的古代药方卷轴", 
    "在众神之战的余烬中静静绽放", "编织着破碎的空间裂缝", "倒映在水中的影子是巨龙形态", 
    "随着大地的脉动有节奏地呼吸", "散发出如同星辰般的孢子雾气", "在冰雪封印中燃烧着冷火"
]

# ============================================================
# 📝 系统提示词 (针对风格锁定和组合最大化优化)
# ============================================================
SYSTEM_PROMPT = """You are a master Image Prompt Engineer specializing in Oriental Materia Medica (Bencao Gangmu) and Mythical Classics (Shan Hai Jing).
Task: Create a masterpiece image prompt based on the user's selected plants, location, action, composition, and SPECIFIC style.

CRITICAL RULES:
1.  **Subject Focus**: The provided 'Bencao Gangmu' plant(s) MUST be the main subject(s). Imagine their mythical, divine form.
2.  **Style Locking**: You MUST only use the ONE specified style from the input list. Do NOT invent new styles (e.g., no '3D', 'Pixar', 'Ghibli').
3.  **Composition Execution**: You MUST execute the provided 'Composition' method to arrange the plants visually.
4.  **No Western Fantasy**: Do NOT use red pandas, tulips, or generic western fantasy elements. Stick to the Chinese/Mythical palette.

Output Valid JSON Only:
{
  "zh_summary": "简短描述 (必须包含输入的植物名和风格名，如：中国水墨风的人参与曼陀罗共生图)",
  "en_prompt": "Detailed English prompt (80-120 words). Focus on divine textures, cinematic lighting (within the style's limits), and the unique visual arrangement of the plants."
}"""

def build_user_message():
    # 组合逻辑：最大化不同可能性
    
    # 1. 决定植物组合方式：60% 概率单一主体，40% 概率双主体组合
    if random.random() > 0.4:
        # 单一主体模式
        plant_main = random.choice(PLANTS_CORE)
        composition = random.choice([COMPOSITIONS[0], COMPOSITIONS[4], COMPOSITIONS[7]]) # 选择适合单一植物的组合
        plant_instruction = f"Main Subject: {plant_main}"
    else:
        # 双主体组合模式
        plant_main = random.choice(PLANTS_CORE)
        plant_env = random.choice(PLANTS_ENV)
        composition = random.choice([COMPOSITIONS[1], COMPOSITIONS[2], COMPOSITIONS[3], COMPOSITIONS[5], COMPOSITIONS[6]])
        plant_instruction = f"Subjects: {plant_main} (core) and {plant_env} (environmental/secondary)"

    # 2. 随机抽取其他元素
    loc = random.choice(LOCATIONS)
    act = random.choice(ACTIONS)
    style = random.choice(STYLES) # 严格从中抽取四种风格之一
    
    # 构造发送给 AI 的指令，强迫它围绕这两个名字创作
    return f"""Generate a breathtaking scene using these oriental elements:
- {plant_instruction}
- Location: {loc}
- Visual Composition: {composition}
- Action/Phenomenon: {act}
- REQUIRED Style: {style}

Requirement: Combine the plants and location into a divine, high-end art piece. The {plant_main} must be the primary focus."""

# ============================================================
# 🌐 API 调用与 JSON 处理逻辑
# ============================================================

def extract_json(text):
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(text[start:end])
    except:
        pass
    return None

async def call_api(session, message, config):
    def _sync_call():
        client = Anthropic(api_key=config["api_key"], base_url=config["api_base"])
        # 注意：这里保持你的 MiniMax/Anthropic 调用逻辑
        response = client.messages.create(
            model=config["model"],
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            temperature=0.85 # 适当提高温度增加多样性
        )
        return "".join([block.text for block in response.content if hasattr(block, 'text')])
    return await asyncio.to_thread(_sync_call)

async def generate_one(session, index, config, semaphore, results, failed):
    user_msg = build_user_message()
    async with semaphore:
        for attempt in range(3):
            try:
                raw_response = await call_api(session, user_msg, config)
                parsed_json = extract_json(raw_response)
                
                if not parsed_json or "en_prompt" not in parsed_json:
                    raise Exception("Invalid API response format")

                en_prompt = parsed_json["en_prompt"].strip()
                zh_summary = parsed_json.get("zh_summary", "神话秘境")

                # Midjourney 参数适配：为不同的风格选择最佳参数
                if "Ink-wash" in en_prompt or "Chinese Xianxia" in en_prompt:
                    # 中国风：开启 niji 6 并适当调整 stylize
                    mj_params = " --ar 16:9 --niji 6 --stylize 300"
                elif "Ukiyo-e" in en_prompt:
                    # 日本版画：高 stylize 以强调线条
                    mj_params = " --ar 16:9 --niji 6 --stylize 500"
                else:
                    # 意大利插画：普通的 v 6.1 或 niji 6 皆可，这里选择 niji 6 以保持整体动漫艺术感
                    mj_params = " --ar 16:9 --niji 6 --stylize 350"
                
                results.append({
                    "id": index + 1,
                    "filename": f"oriental_{str(index + 1).zfill(3)}.jpg",
                    "zh_summary": zh_summary,
                    "prompt": en_prompt + mj_params
                })
                print(f"✅ [{index+1:3d}] {zh_summary}")
                return
            except Exception as e:
                if attempt < 2: await asyncio.sleep(3)
                else: 
                    print(f"❌ [{index+1:3d}] 失败: {e}")
                    failed.append({"id": index + 1, "error": str(e)})

# ============================================================
# 💾 保存结果
# ============================================================

def save_results(results, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    txt_path = out / f"myth_prompts_{ts}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for r in sorted(results, key=lambda x: x["id"]):
            f.write(f"【{r['id']:03d}】 {r['zh_summary']}\n")
            f.write(f"{r['prompt']}\n\n")

    json_path = out / f"myth_mapping_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        mapping = {r["filename"]: r["prompt"] for r in sorted(results, key=lambda x: x["id"])}
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"\n📄 生成完毕！已保存 {len(results)} 组 Prompt。")
    print(f"- TXT (阅读用): {txt_path}")
    print(f"- JSON (代码调用用): {json_path}")

# ============================================================
# 🚀 主程序
# ============================================================

async def main(count):
    print(f"🚀 任务启动：正在从100+草本库中最大化组合生成 {count} 组场景...")
    print(f"🔒 风格已锁定为：水墨、版画、意大利插画、中国古风")
    results, failed = [], []
    semaphore = asyncio.Semaphore(CONFIG["concurrency"])
    
    async with aiohttp.ClientSession() as session:
        tasks = [generate_one(session, i, CONFIG, semaphore, results, failed) for i in range(count)]
        await asyncio.gather(*tasks)

    if results:
        save_results(results, CONFIG["output_dir"])
    if failed:
        print(f"⚠ 有 {len(failed)} 组任务失败。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # 默认生成数量建议设高一些，以体现组合效果
    parser.add_argument("--count", type=int, default=15, help="生成数量")
    args = parser.parse_args()
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main(args.count))