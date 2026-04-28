import json
import subprocess
from pathlib import Path
from fnmatch import fnmatch
from autoresearch.skill_research.strategies import VerificationScenario, ExpectedFile, ExpectedProperty
from autoresearch.skill_research.metrics import ScenarioResult, SkillMetrics


class SkillVerifier:
    def __init__(self, project_root: Path, skill_path: Path | None = None):
        self.project_root = project_root
        self.output_dir = project_root / "output"
        if skill_path is None:
            skill_path = project_root / ".trae" / "skills" / "video-clip" / "SKILL.md"
        self.skill_path = skill_path

    def load_skill(self) -> str:
        if not self.skill_path.exists():
            return ""
        return self.skill_path.read_text(encoding="utf-8")

    def verify_scenario(self, scenario: VerificationScenario) -> ScenarioResult:
        result = ScenarioResult(scenario_id=scenario.scenario_id)
        skill_text = self.load_skill()

        result.workflow_selection_correct = self._check_workflow_selection(
            skill_text, scenario
        )
        result.parameter_compliance = self._check_parameter_compliance(
            skill_text, scenario
        )
        result.output_completeness = self._check_output_completeness(scenario)
        result.quality_compliance = self._check_quality_compliance(scenario)
        result.delivery_score = self._compute_delivery_score(result)
        result.details = self._collect_details(scenario)
        return result

    def verify_all(
        self, scenarios: dict[str, VerificationScenario]
    ) -> SkillMetrics:
        metrics = SkillMetrics()
        for scenario in scenarios.values():
            sr = self.verify_scenario(scenario)
            metrics.scenario_results.append(sr)
        metrics.compute_derived()
        return metrics

    def _check_workflow_selection(
        self, skill_text: str, scenario: VerificationScenario
    ) -> bool:
        if not skill_text:
            return False
        workflow_keywords = {
            "工作流1：一期一剪": ["一期一剪", "精剪", "完整版", "full_episode"],
            "工作流2：内容原子化": ["内容原子化", "短视频", "切片", "高光", "atomization"],
            "工作流3：知识混剪": ["知识混剪", "Wiki", "主题", "章节", "mashup"],
            "工作流4：全平台出品": ["全平台出品", "平台适配", "导出", "platform"],
            "工作流5：素材库打包": ["素材库打包", "打包", "交付", "版权声明", "packaging"],
        }
        expected = scenario.expected_workflow
        for wf_key, keywords in workflow_keywords.items():
            if any(k in expected for k in keywords):
                return any(k in skill_text for k in keywords)
        if "全部工作流" in expected:
            return all(
                any(k in skill_text for k in keywords)
                for keywords in workflow_keywords.values()
            )
        if "组合执行" in expected or "需明确意图" in expected:
            return "决策树" in skill_text or "主动" in skill_text or "询问" in skill_text
        return False

    def _check_parameter_compliance(
        self, skill_text: str, scenario: VerificationScenario
    ) -> float:
        if not scenario.expected_properties:
            return 100.0
        if not skill_text:
            return 0.0
        checks_passed = 0
        total = len(scenario.expected_properties)
        for prop in scenario.expected_properties:
            if self._property_in_skill(skill_text, prop):
                checks_passed += 1
        return round(checks_passed / total * 100, 1)

    PROPERTY_KEYWORD_MAP = {
        "video_resolution": ["视频", "分辨率", "1920x1080", "横版", "16:9"],
        "vertical_resolution": ["竖版", "1080x1920", "9:16", "竖屏"],
        "subtitle_accuracy": ["字幕", "准确率", "99.9", "零容忍", "勘误"],
        "audio_lufs": ["响度", "LUFS", "-14", "标准化"],
        "vertical_no_crop": ["竖版", "裁剪", "模糊背景", "填充", "不裁剪"],
        "clip_count": ["切片", "片段", "5-8", "5～8", "高光"],
        "clip_duration_range": ["时长", "15秒", "3分钟", "分钟"],
        "each_clip_independent": ["独立", "可理解", "无需上下文"],
        "has_hook": ["钩子", "hook", "前3秒", "注意力"],
        "chapter_count": ["章节", "章", "3个"],
        "chapter_duration": ["每章", "2-4分钟", "2～4"],
        "naming_convention": ["命名", "wiki_", "规范"],
        "cross_timeline": ["跨时间线", "跨", "素材调度"],
        "bilibili_resolution": ["B站", "bilibili", "1920x1080"],
        "douyin_resolution": ["抖音", "douyin", "1080x1920"],
        "youtube_resolution": ["YouTube", "1920x1080"],
        "douyin_subtitle_chars": ["抖音", "每行", "12字", "≤12"],
        "each_lufs_compliant": ["响度", "LUFS", "达标", "标准化"],
        "dir_structure_complete": ["目录", "结构", "标准化"],
        "copyright_exists": ["版权", "COPYRIGHT", "声明"],
        "release_cards_exist": ["发布信息卡", "RELEASE_CARDS"],
        "all_formats_present": ["格式", "齐全", "横版", "竖版"],
        "av_sync_ms": ["同步", "50ms", "音视频"],
        "lufs_deviation": ["响度", "偏差", "±1dB", "1dB"],
        "copyright_clear": ["版权", "清晰", "声明"],
        "agent_clarifies_intent": ["主动", "询问", "澄清", "确认"],
        "no_wrong_workflow": ["决策", "匹配", "选择"],
        "workflow_order_correct": ["顺序", "按序", "先", "再"],
        "all_workflows_completed": ["完成", "所有", "全部"],
        "intermediate_reuse": ["复用", "中间产物", "前序"],
    }

    def _property_in_skill(self, skill_text: str, prop: ExpectedProperty) -> bool:
        value_str = str(prop.expected_value) if prop.expected_value is not None else ""
        name_in_skill = prop.name.replace("_", " ") in skill_text.lower() or prop.name in skill_text
        value_in_skill = value_str in skill_text
        semantic_match = False
        keywords = self.PROPERTY_KEYWORD_MAP.get(prop.name, [])
        if keywords:
            matched = sum(1 for k in keywords if k in skill_text)
            semantic_match = matched >= max(1, len(keywords) // 2)
        if prop.check_type == "equals" and isinstance(prop.expected_value, bool):
            return name_in_skill or semantic_match
        if prop.check_type in ("equals", "range", ">=", "<="):
            return (name_in_skill and value_in_skill) or (semantic_match and value_in_skill) or semantic_match
        if prop.check_type == "matches":
            import re
            return bool(re.search(value_str, skill_text)) or semantic_match
        return name_in_skill or semantic_match

    def _check_output_completeness(self, scenario: VerificationScenario) -> float:
        if not scenario.expected_files:
            return 100.0
        if not scenario.output_dir_pattern:
            return 50.0
        search_dir = self.output_dir
        if not search_dir.exists():
            return self._check_output_doc_readiness(scenario)
        all_files = self._collect_output_files(search_dir)
        checks_passed = 0
        total = 0
        for ef in scenario.expected_files:
            total += 1
            if self._file_pattern_exists(all_files, ef.pattern, search_dir):
                checks_passed += 1
        if total == 0:
            return 100.0
        file_score = round(checks_passed / total * 100, 1)
        if checks_passed == total:
            return file_score
        doc_score = self._check_output_doc_readiness(scenario)
        file_coverage = checks_passed / total
        actual_weight = file_coverage * 0.7
        doc_weight = 1.0 - actual_weight
        return round(file_score * actual_weight + doc_score * doc_weight, 1)

    OUTPUT_KEYWORD_MAP = {
        "full_episode/": ["完整版", "full_episode", "一期一剪"],
        "clips/": ["切片", "短视频", "clips", "内容原子化"],
        "platforms/": ["平台", "platforms", "全平台", "B站", "抖音", "YouTube"],
        "COPYRIGHT.md": ["版权", "COPYRIGHT", "声明"],
        "RELEASE_CARDS.json": ["发布信息卡", "RELEASE_CARDS"],
        "summary.json": ["总览", "summary", "项目总览"],
        "wiki_series/": ["知识混剪", "wiki", "Wiki", "章节"],
        "assets/": ["素材", "assets", "素材库"],
        "bilibili/": ["B站", "bilibili"],
        "douyin/": ["抖音", "douyin"],
        "youtube/": ["YouTube"],
        "subtitles/": ["字幕", "subtitle"],
        "audio/": ["音频", "audio"],
        "covers/": ["封面", "cover"],
        "bilibili/*.mp4": ["B站", "bilibili", "1920x1080"],
        "douyin/*.mp4": ["抖音", "douyin", "1080x1920"],
        "youtube/*.mp4": ["YouTube", "1920x1080"],
    }

    def _check_output_doc_readiness(self, scenario: VerificationScenario) -> float:
        skill_text = self.load_skill()
        if not skill_text or not scenario.expected_files:
            return 0.0
        checks_passed = 0
        total = len(scenario.expected_files)
        for ef in scenario.expected_files:
            pattern = ef.pattern.rstrip("/")
            basename = pattern.split("/")[-1] if "/" in pattern else pattern
            clean_base = basename.replace("*", "").replace(".", " ").strip()
            keywords = self.OUTPUT_KEYWORD_MAP.get(ef.pattern, [])
            if not keywords:
                dir_part = pattern.split("/")[0] if "/" in pattern else ""
                keywords = self.OUTPUT_KEYWORD_MAP.get(dir_part + "/", [])
            name_in_skill = clean_base in skill_text or pattern in skill_text
            semantic_match = False
            if keywords:
                matched = sum(1 for k in keywords if k in skill_text)
                semantic_match = matched >= max(1, len(keywords) // 2)
            if name_in_skill or semantic_match:
                checks_passed += 1
        if total == 0:
            return 100.0
        return round(checks_passed / total * 100, 1)

    def _collect_output_files(self, root: Path) -> list[str]:
        files = []
        for p in root.rglob("*"):
            if p.is_file():
                files.append(str(p.relative_to(root)).replace("\\", "/"))
        return files

    def _file_pattern_exists(
        self, all_files: list[str], pattern: str, root: Path
    ) -> bool:
        for f in all_files:
            if fnmatch(f, pattern) or fnmatch(Path(f).name, pattern):
                return True
            if pattern in f:
                return True
        return False

    QUALITY_CHECK_KEYWORD_MAP = {
        "字幕逐句零容忍勘误": ["零容忍", "逐句", "勘误"],
        "音视频同步≤50ms": ["同步", "50ms"],
        "响度标准化至目标LUFS": ["响度", "标准化", "LUFS"],
        "竖版模糊背景填充非裁剪": ["模糊背景", "填充", "裁剪"],
        "高光检测覆盖金句/情绪/悬念/故事/争议": ["高光", "金句", "情绪", "悬念"],
        "每个切片独立可理解无需上下文": ["独立", "可理解", "上下文"],
        "前3秒有明确钩子": ["钩子", "前3秒", "3秒"],
        "竖版9:16模糊背景填充": ["9:16", "模糊背景", "竖版"],
        "知识图谱构建完整": ["知识图谱", "构建"],
        "章节间有逻辑递进": ["章节", "递进", "逻辑"],
        "每章独立可看": ["独立", "可看"],
        "命名规范一致": ["命名", "规范"],
        "读取platforms.yaml平台规格": ["platforms.yaml", "平台", "规格"],
        "每个平台独立响度标准化": ["响度", "标准化", "平台"],
        "元数据嵌入": ["元数据", "嵌入"],
        "目录结构符合SKILL规范": ["目录", "结构", "规范"],
        "版权声明包含素材来源/授权/CC协议": ["版权", "来源", "授权", "CC"],
        "发布信息卡含标题/描述/标签/封面规格": ["发布信息卡", "标题", "描述", "标签"],
        "逐句零容忍字幕勘误": ["零容忍", "逐句", "勘误"],
        "音视频同步检查": ["同步", "音视频"],
        "响度达标检查": ["响度", "达标"],
        "竖版画面完整性检查": ["竖版", "完整性", "裁剪"],
        "版权声明存在性检查": ["版权", "声明"],
        "模糊请求时主动询问确认": ["主动", "询问", "确认"],
        "不假设用户意图": ["假设", "意图"],
        "先精剪再切片再导出再打包": ["精剪", "切片", "导出", "打包"],
        "前序工作流产出作为后序输入": ["前序", "后序", "产出", "输入"],
        "不重复处理": ["重复", "复用"],
    }

    def _check_quality_compliance(self, scenario: VerificationScenario) -> float:
        if not scenario.quality_checks:
            return 100.0
        skill_text = self.load_skill()
        if not skill_text:
            return 0.0
        checks_passed = 0
        for check in scenario.quality_checks:
            mapped = self.QUALITY_CHECK_KEYWORD_MAP.get(check)
            if mapped:
                matched = sum(1 for k in mapped if k in skill_text)
                if matched >= max(1, len(mapped) // 2):
                    checks_passed += 1
                    continue
            keywords = check.replace("≤", "").replace("≥", "").replace("±", "").split()
            if any(k in skill_text for k in keywords if len(k) > 1):
                checks_passed += 1
        return round(checks_passed / len(scenario.quality_checks) * 100, 1)

    def _compute_delivery_score(self, result: ScenarioResult) -> float:
        weights = {
            "workflow_selection": 0.25,
            "parameter": 0.20,
            "output": 0.30,
            "quality": 0.25,
        }
        score = (
            (100.0 if result.workflow_selection_correct else 0.0) * weights["workflow_selection"]
            + result.parameter_compliance * weights["parameter"]
            + result.output_completeness * weights["output"]
            + result.quality_compliance * weights["quality"]
        )
        return round(score, 1)

    def _collect_details(self, scenario: VerificationScenario) -> dict:
        details = {
            "scenario_id": scenario.scenario_id,
            "expected_workflow": scenario.expected_workflow,
            "expected_file_count": len(scenario.expected_files),
            "expected_property_count": len(scenario.expected_properties),
            "quality_check_count": len(scenario.quality_checks),
        }
        search_dir = self.output_dir
        if search_dir.exists() and scenario.output_dir_pattern:
            pattern = scenario.output_dir_pattern.replace("output/", "").replace("output\\", "")
            if not pattern:
                return details
            try:
                matching_dirs = list(search_dir.glob(pattern))
            except ValueError:
                matching_dirs = []
            details["matching_output_dirs"] = len(matching_dirs)
            if matching_dirs:
                sample_dir = matching_dirs[0]
                files_in_dir = list(sample_dir.rglob("*"))
                details["sample_dir_file_count"] = len([f for f in files_in_dir if f.is_file()])
                details["sample_dir_files"] = [
                    f.name for f in files_in_dir if f.is_file()
                ][:20]
        return details
