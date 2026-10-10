#!/usr/bin/env python3
"""Render source-bound benchmark diagrams (SVG; optional PNG with existing Pillow).

No model calls or runtime dependencies. PNG export is an authoring convenience:
python3 scripts/render_benchmark_figures.py --png --font /path/to/CJK-font.ttc
"""
import argparse
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PAPER, INK, MUTED, LINE = '#FFFFFF', '#202B40', '#647087', '#DEE4ED'
GREEN, BLUE, OCHRE = '#19776B', '#405DC6', '#B96532'
COLORS = [BLUE, GREEN, OCHRE]
FILLS = ['#EFF2FC', '#EBF5F2', '#FCF2E9']
LABELS = ['择校推荐', '规划与决策', '两阶段任务']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


class Figure:
    def __init__(self, title, description, height=980, font=None):
        self.width, self.height, self.font_path = 1600, height, font
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}" viewBox="0 0 1600 {height}" role="img" aria-labelledby="title desc">',
                      '<title id="title">' + escape(title) + '</title>',
                      '<desc id="desc">' + escape(description) + '</desc>']
        self.draw = None
        self.fonts = {}
        if font:
            from PIL import Image, ImageDraw
            self.raster = Image.new('RGB', (1600, height), PAPER)
            self.draw = ImageDraw.Draw(self.raster)
        self.rect(0, 0, 1600, height, PAPER)

    def font(self, size, bold=False):
        from PIL import ImageFont
        key = size, bold
        if key not in self.fonts:
            try:
                self.fonts[key] = ImageFont.truetype(str(self.font_path), size, index=int(bold))
            except OSError:
                self.fonts[key] = ImageFont.truetype(str(self.font_path), size)
        return self.fonts[key]

    def rect(self, x, y, w, h, fill='white', stroke=None, radius=0):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke or "none"}"/>')
        if self.draw:
            box = (x, y, x+w, y+h)
            if radius:
                self.draw.rounded_rectangle(box, radius, fill=fill, outline=stroke)
            else:
                self.draw.rectangle(box, fill=fill, outline=stroke)

    def line(self, x1, y1, x2, y2, color=LINE, width=2):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>')
        if self.draw:
            self.draw.line((x1, y1, x2, y2), fill=color, width=width)

    def circle(self, x, y, r, fill='white', stroke=None, width=2):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>')
        if self.draw:
            self.draw.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=stroke,width=width)

    def route(self, points, color=MUTED, width=2, arrow=True):
        for a,b in zip(points,points[1:]):
            self.line(*a,*b,color,width)
        if arrow:
            self.arrow(*points[-2],*points[-1],color)

    def badge(self, x, y, value, color=BLUE):
        self.circle(x,y,17,color)
        self.text(x,y-11,value,19,'white',True,'middle')

    def document(self, x, y, w, h, label, color=BLUE):
        self.rect(x,y,w,h,'white',LINE,8)
        self.line(x+22,y+51,x+w-22,y+51,LINE,1)
        self.rect(x+22,y+22,7,7,color)
        self.text(x+40,y+15,label,17,color,True)

    def check(self, x, y, color=GREEN):
        self.line(x,y+6,x+6,y+12,color,3)
        self.line(x+6,y+12,x+18,y-2,color,3)

    def arrow(self, x1, y1, x2, y2, color=MUTED):
        import math
        self.line(x1, y1, x2, y2, color)
        a = math.atan2(y2-y1, x2-x1)
        for delta in (-.5, .5):
            self.line(x2, y2, x2-12*math.cos(a+delta), y2-12*math.sin(a+delta), color)

    def text(self, x, y, value, size=22, color=INK, bold=False, anchor='start'):
        # Consistent top-origin API; Markdown uses PNG for font-independent layout.
        self.parts.append(f'<text x="{x}" y="{y+size*.86}" font-family="Hiragino Sans GB, Noto Sans CJK SC, Microsoft YaHei, sans-serif" font-size="{size}" font-weight="{600 if bold else 400}" text-anchor="{anchor}" fill="{color}">{escape(str(value))}</text>')
        if self.draw:
            self.draw.text((x, y), str(value), font=self.font(size, bold), fill=color,
                           anchor={'start': 'lt', 'middle': 'mt', 'end': 'rt'}[anchor])

    def paragraph(self, x, y, value, max_width, size=21, color=MUTED, leading=1.6):
        lines = []
        for paragraph in value.split('\n'):
            line = ''
            for char in paragraph:
                candidate = line + char
                width = (self.draw.textlength(candidate, font=self.font(size)) if self.draw else
                         sum(size if unicodedata.east_asian_width(c) in 'WF' else size*.55 for c in candidate))
                if width > max_width and line:
                    lines.append(line); line = char
                else:
                    line = candidate
            lines.append(line)
        for i, line in enumerate(lines):
            self.text(x, y+i*size*leading, line, size, color)
        return y + len(lines)*size*leading

    def header(self, number, title, subtitle):
        self.rect(64,44,8,22,BLUE)
        self.text(88,44,'保研 Agent Benchmark',20,INK,True)
        self.text(1536,46,number+'  /  SUBSET 20',17,MUTED,anchor='end')
        self.text(64,108,title,46,INK,True)
        self.text(64,179,subtitle,22,MUTED)

    def footer(self, note):
        self.line(64,self.height-62,1536,self.height-62,LINE,1)
        self.text(64,self.height-40,note,16,MUTED)
        self.text(1536,self.height-40,'1.0.1  ·  public-dev-20-v1',16,MUTED,anchor='end')

    def save(self, directory, name):
        (directory / (name+'.svg')).write_text('\n'.join(self.parts+['</svg>'])+'\n', encoding='utf-8')
        if self.draw:
            self.raster.save(directory / (name+'.png'), optimize=True)


class EditorialFigure(Figure):
    """Use the actual bold face for the macOS CJK collection in homepage figures."""
    def font(self, size, bold=False):
        face = super().font(size, bold)
        family, style = face.getname()
        if bold and 'Hiragino Sans GB' in family and style == 'W3':
            from PIL import ImageFont
            try:
                candidate = ImageFont.truetype(str(self.font_path), size, index=2)
                if candidate.getname()[1] == 'W6':
                    self.fonts[size, bold] = face = candidate
            except OSError:
                pass
        return face


def load_data():
    paths = ['config/selections/public-dev-20-v1.json']
    selected = first = read(ROOT / paths[0])
    rows = selected['tasks']
    if selected['task_ids'] != [r['task_id'] for r in rows] or len(set(selected['task_ids'])) != len(rows):
        raise ValueError('Selection IDs/count mismatch')
    for row in rows:
        for kind in ('task', 'rubric'):
            name = row[kind+'_path']
            # Selection fingerprints use the repository canonical JSON encoding.
            from benchmark.core import digest
            if digest(read(ROOT/name)) != row['fingerprints'][kind]:
                raise ValueError('Selected content changed: '+name)
            paths.append(name)
    counts = Counter(r['category'] for r in rows)
    cases = Counter(r['case_group_id'] for r in rows)
    stages = sum(r['stage_count'] for r in rows)
    if (len(rows), len(cases), stages) != (20, 20, 24):
        raise ValueError('This figure layout is for the initial 20-task scope')
    case = read(ROOT/'data/staged-dev/N16-02/task.json')
    rubric = read(ROOT/'data/staged-dev/N16-02/rubric.json')
    return selected, first, counts, cases, case, rubric, paths


def overview(out, data, font, language='zh'):
    """Bilingual overview: staged input, one continuing session, separate review."""
    selected, _, counts, cases, *_ = data
    en = language == 'en'
    ink, muted, paper, border = '#30283F', '#746C7E', '#FAF7F1', '#E4D9CD'
    purple, lavender = '#7854A6', '#EEE5F5'
    coral, peach, gold, butter = '#D96351', '#FBE0D7', '#B57D17', '#F8E6AB'
    title = 'When facts change, does the advice keep up?' if en else '信息变了，建议如何更新？'
    f = EditorialFigure(title, 'N16-02: S0 and S1 enter one native agent session in order; both answers go to independent review. 20 tasks, 20 cases, 24 stages.', 960, font)
    f.rect(12, 12, 1576, 936, paper, radius=36)
    f.text(68, 53, 'BAOYAN AGENT BENCHMARK', 18, purple, True)
    f.text(1532, 53, '01 / HOW IT WORKS', 18, muted, anchor='end')
    f.text(68, 102, title, 44, ink, True)
    f.text(68, 166, 'A real two-stage task: new evidence enters only after the first answer.' if en else
           '用一道真实两阶段题，展示从背景理解、信息补充到独立评审的完整过程。', 23, muted)

    # Inputs retain a strong visual distinction between the original and later facts.
    for y, color, fill, number, label in [
        (257, coral, peach, '01', 'INITIAL FACTS / S0' if en else '初始信息 / S0'),
        (501, gold, butter, '02', 'NEW EVIDENCE / S1' if en else '补充信息 / S1')]:
        f.rect(68, y, 421, 208, fill, radius=20)
        f.circle(104, y+35, 17, color)
        f.text(104, y+24, number, 17, 'white', True, 'middle')
        f.text(134, y+24, label, 21, ink, True)
    if en:
        for i, line in enumerate(['No declared major yet.', 'Mechanical engineering or', 'smart manufacturing?']):
            f.text(94, 324+i*31, line, 24, ink, True)
        f.text(94, 428, 'Rank 19/123   ·   CET-6 458', 19, muted)
        for i, line in enumerate(['Mechanical innovation,', 'student research, a smart lock.']):
            f.text(94, 572+i*32, line, 22, ink, True)
        f.text(94, 661, 'Still no formally declared major.', 19, muted)
    else:
        f.text(94, 331, '“还没正式分流，', 29, ink, True)
        f.text(94, 374, '想申请机械或智能制造。”', 29, ink, True)
        f.text(94, 429, '专业排名 19/123  ·  六级 458', 21, muted)
        f.text(94, 578, '机械创新 · 省级大创 · 智能门锁', 23, ink, True)
        f.text(94, 650, '学籍仍是工科大类，未正式分流', 22, muted)

    # One container makes continuation explicit without implying two agents.
    f.rect(557, 257, 465, 452, lavender, radius=20)
    f.circle(595, 294, 18, purple)
    f.text(595, 282, 'A', 21, 'white', True, 'middle')
    f.text(626, 280, 'ONE NATIVE SESSION' if en else '同一个原生 Agent 会话', 23, ink, True)
    f.text(584, 327, 'Model + tools + authentication' if en else '模型 + 工具 + 认证配置', 21, muted)
    f.rect(583, 374, 413, 100, '#FFFFFF', radius=12)
    f.text(608, 392, 'A0  First answer' if en else 'A0  首轮作答', 26, ink, True)
    f.text(608, 434, 'Use only the initial facts' if en else '只依据当前背景提出建议', 21, muted)
    f.arrow(789, 484, 789, 549, purple)
    f.text(812, 509, 'Then release S1' if en else '完成后再释放 S1', 18, purple, True)
    f.rect(583, 561, 413, 119, '#FFFFFF', radius=12)
    f.text(608, 580, 'A1  Revised advice' if en else 'A1  更新建议', 26, ink, True)
    f.text(608, 625, 'Reassess fit; retain constraints' if en else '结合新证据，保留原有约束', 21, muted)
    f.arrow(501, 412, 545, 412, coral)
    f.arrow(501, 622, 545, 622, gold)

    f.rect(1090, 257, 442, 452, '#FFFEFC', border, 20)
    f.text(1118, 282, 'INDEPENDENT REVIEW' if en else '独立评审', 26, ink, True)
    f.text(1118, 328, 'Both answers + task rubric' if en else '两轮原文 + 逐题评分标准', 21, muted)
    f.arrow(1034, 485, 1078, 485, purple)
    criteria = ([('Read the constraints', 'Rank is not eligibility.'),
                 ('Use new evidence', 'Check project contributions.'),
                 ('Plan the next step', 'Explain tradeoffs and checks.')] if en else
                [('理解背景与条件', '不把排名直接当作推免资格'),
                 ('利用新增信息', '核验项目贡献，重新评估适配'),
                 ('落实申请行动', '解释取舍与需要验证的条件')])
    for i, (label, note) in enumerate(criteria):
        y = 386+i*101
        if i: f.line(1118, y-20, 1504, y-20, border, 1)
        f.circle(1135, y+16, 16, purple)
        f.check(1127, y+11, 'white')
        f.text(1165, y, label, 23, ink, True)
        f.text(1165, y+40, note, 19, muted)

    # Scope stays separate from measured performance.
    metrics = [(68, len(selected['tasks']), 'tasks' if en else '道题',
                '6 recommendation / 10 planning / 4 staged' if en else '6 择校 / 10 规划 / 4 两阶段'),
               (594, len(cases), 'student cases' if en else '个学生案例',
                'One selected task per case' if en else '每个案例选取一道题'),
               (1120, sum(r['stage_count'] for r in selected['tasks']), 'stages' if en else '个作答阶段',
                'Two stages, one task score' if en else '两阶段合并计分，仍算一道题')]
    for x, value, unit, note in metrics:
        f.text(x, 751, value, 56, ink, True)
        f.text(x+91, 777, unit, 23, ink, True)
        f.text(x, 823, note, 18, muted)
    f.rect(68, 878, 1464, 42, ink, radius=12)
    f.text(800, 890, 'S0 → A0 → S1 → A1  ·  Rubrics stay with the reviewer  ·  Example: N16-02; no model scores shown' if en else
           'S0 → A0 → S1 → A1  ·  评分标准仅供评审使用  ·  例题 N16-02，图示不包含模型成绩',
           18, '#FFFFFF', True, 'middle')
    f.save(out, 'benchmark-overview')


def distribution(out,data,font):
    selected,_,counts,cases,*_=data
    f=Figure('首批20题：题型与阶段分布','6道择校、10道规划、4道两阶段任务；每个点是一道题，双点连线表示同一题的两个阶段。',1000,font)
    f.header('02 / COMPOSITION','20 道题，三种决策挑战','覆盖20个学生案例；题型互斥统计，阶段数单独计算。')
    labels=['在约束下选项目','在有限资源中做取舍','在新信息后更新判断']
    for i,category in enumerate(LABELS):
        y=279+i*171;color=COLORS[i];n=counts[category]
        f.text(64,y,category,27,color,True)
        f.text(64,y+45,labels[i],20,MUTED)
        for j in range(10):
            x=467+j*74
            f.circle(x,y+33,22,color if j<n else '#F1F3F7')
            if j<n:
                f.text(x,y+21,str(j+1),19,'white',True,'middle')
        f.text(1320,y-7,str(n),61,color,True,anchor='end')
        f.text(1341,y+20,'题',23,INK)
        f.text(1536,y+16,f'{n/20:.0%}',32,MUTED,anchor='end')
        f.line(64,y+121,1536,y+121,LINE,1)
    f.text(64,802,'为什么是24个阶段？',25,INK,True)
    f.circle(511,824,13,BLUE)
    f.text(547,808,'16 × 1',29,INK,True)
    f.text(711,808,'＋',29,MUTED)
    f.circle(829,824,13,OCHRE);f.circle(877,824,13,OCHRE)
    f.line(843,824,863,824,OCHRE,2)
    f.text(914,808,'4 × 2',29,INK,True)
    f.text(1106,808,'＝',29,MUTED)
    f.text(1222,792,'24',58,INK,True)
    f.text(1321,820,'个作答阶段',23,INK)
    f.text(547,866,'单阶段题',18,MUTED)
    f.text(914,866,'两阶段题',18,MUTED)
    f.footer('每个实心圆代表一道题；浅灰圆仅为10题比较刻度，不代表缺题。')
    f.save(out,'dataset-distribution')


def flow(out,data,font):
    f=Figure('逐阶段作答与独立评审','组织者仅释放当前阶段；S0到A0完成后才释放S1到A1；两轮答卷及组织者评分材料汇入独立评审。',1100,font)
    f.header('03 / PROTOCOL','当前能看到什么，决定当前如何作答','题目逐阶段释放；答题与评审分离，每一步留下可复核的原始记录。')

    # Distinct lanes: current candidate input vs organizer-only reference material.
    f.rect(64,263,1054,463,'#F7F9FE',radius=12)
    f.rect(1150,263,386,463,'#FCF8F3',radius=12)
    f.text(90,286,'答题侧  /  当前题的独立会话',22,BLUE,True)
    f.text(1175,286,'组织者侧  /  保管材料',22,OCHRE,True)
    nodes=[(92,'S0','初始题面',BLUE),(350,'A0','首次答卷',BLUE),
           (608,'S1','补充事实',OCHRE),(866,'A1','更新答卷',BLUE)]
    for x,code,title,color in nodes:
        f.document(x,375,221,164,code,color)
        f.text(x+110,459,title,27,INK,True,'middle')
    for x in (313,571,829):f.arrow(x+4,462,x+31,462,BLUE)
    f.text(590,333,'A0 完成后才释放 S1',21,OCHRE,True,'middle')
    f.line(590,365,590,438,OCHRE,1)
    f.text(590,619,'两轮顺序作答，保留各轮原始交付',23,BLUE,True,'middle')
    f.text(90,685,'跨题重建 HOME、工作目录和会话；同题保留自己的上下文。',20,MUTED)
    for y,title,note in [(372,'逐题 rubric','规则与参考资料'),(478,'未来阶段','到达该阶段时才释放'),(584,'其他题与答卷','不进入当前题的工作区')]:
        f.rect(1175,y,4,54,OCHRE)
        f.text(1192,y,title,24,INK,True)
        f.text(1192,y+36,note,18,MUTED)

    # A0/A1 record collection is separate from the time axis above.
    f.line(460,539,460,556,BLUE,1);f.line(976,539,976,556,BLUE,1)
    f.line(460,556,1077,556,BLUE,1)
    f.route([(1077,556),(1077,751),(296,751),(296,784)],BLUE)
    f.route([(1485,405),(1560,405),(1560,762),(818,762),(818,784)],OCHRE)
    f.rect(64,784,464,150,FILLS[0],radius=8)
    f.rect(584,784,464,150,FILLS[1],radius=8)
    f.rect(1104,784,432,150,'#F4F6F9',radius=8)
    for x,n,title,note,color in [(88,'1','匿名评审包','A0＋A1 合并为一道题',BLUE),
                               (608,'2','独立逐项判断','依据 rubric，保留引句与理由',GREEN),
                               (1128,'3','程序算分','校验、留档、支持重算',INK)]:
        f.text(x,807,n,18,color,True)
        f.text(x+34,802,title,27,INK,True)
        f.text(x,875,note,20,MUTED)
    f.arrow(536,860,576,860,BLUE);f.arrow(1056,860,1096,860,GREEN)
    f.text(64,979,'缺题、失败与待核单列；只有同一题集的完整评分才能形成该题集总分。',22,INK)
    f.footer('方法示意；本地隔离采用进程沙箱，具体认证与网络限制随实验披露。')
    f.save(out,'evaluation-flow')


def case_figure(out,data,font):
    *_,case,rubric,_paths=data
    f=Figure('N16-02：新经历与未变的专业约束','补充工程项目增加适配证据，但不改变正式学籍。评审检查Agent能否同时利用新证据并保留申请资格约束。',1100,font)
    f.header('04 / CASE STUDY','项目经历增加了，专业限制就消失了吗？','N16-02  ·  两阶段原题节选  ·  观察 Agent 如何处理新增证据与不变的约束。')

    # Stable baseline on the left, two explicitly different implications on the right.
    f.document(64,273,413,421,'S0  /  初始背景',BLUE)
    f.text(92,354,'工科大类',37,INK,True)
    f.text(92,410,'尚未正式分流',25,OCHRE,True)
    f.line(92,462,448,462,LINE,1)
    for y,key,value in [(491,'排名','19/123'),(541,'六级','458'),(591,'意向','机械 / 智能制造')]:
        f.text(92,y,key,21,MUTED);f.text(188,y,value,24,INK,True)

    f.text(585,282,'S1  /  新增事实',21,OCHRE,True)
    f.rect(581,330,955,109,FILLS[2],radius=8)
    f.badge(616,366,'+',OCHRE)
    f.text(650,351,'机械创新 · 省级大创 · 智能门锁系统',29,INK,True)
    f.text(650,395,'题面同时重申：学籍仍为工科大类，未正式分流。',20,MUTED)
    f.arrow(493,385,561,385,BLUE)
    f.route([(1048,439),(1048,481),(820,481),(820,510)],GREEN)
    f.route([(1048,481),(1318,481),(1318,510)],OCHRE)
    f.text(583,548,'增加了什么',28,GREEN,True)
    f.rect(583,592,6,96,GREEN)
    f.text(610,590,'研究适配与能力的证据',25,INK,True)
    f.text(610,639,'仍需核验个人分工、成果状态',21,MUTED)
    f.text(1109,548,'没有改变什么',28,OCHRE,True)
    f.rect(1109,592,6,96,OCHRE)
    f.text(1136,590,'正式学籍与专业认定',25,INK,True)
    f.text(1136,639,'仍需核验目标项目的申请条件',21,MUTED)

    f.line(64,741,1536,741,LINE,1)
    f.text(64,776,'评审看什么',22,MUTED)
    f.text(267,765,'用新证据更新适配判断，同时保留资格边界。',33,INK,True)
    f.text(267,820,'可以修改建议，也可以维持建议；两者都需要依据和下一步行动。',22,MUTED)

    # Weight bars carry labels directly, rather than repeating unlabeled color blocks.
    f.text(64,891,'100分',34,INK,True)
    f.text(64,940,'原评分权重',18,MUTED)
    short=['专业风险','英语与排名','成果分工','学位适配','时间备选','证据边界','路线取舍','判断更新']
    for i,node in enumerate(rubric['nodes']):
        x=282+i*157
        f.text(x,889,node['points'],26,BLUE,True)
        f.rect(x,929,132,5,'#ECF0F7')
        f.rect(x,929,132*node['points']/24,5,BLUE)
        f.text(x,951,short[i],17,MUTED)
    f.footer('按各轮当时已知信息评审；两轮合并计1题，同一错误不重复扣分。')
    f.save(out,'case-n16-02')


def guide(out,data,figure_dir,png):
    selected,first,counts,cases,case,rubric,_=data
    lines=['# 保研 Agent Benchmark 图解','','用四张图了解评测范围、题库构成、执行方式和两阶段例题。版本：**1.0.1 / public-dev-20-v1**。','',
           '## 1. 测什么','','![Benchmark总览：20题、20个案例、24个阶段](figures/benchmark-overview.png)','','我们比较原生 Agent 产品及其模型、工具和认证配置。题目要求理解学生背景与升学约束，进行项目选择、路线取舍和行动规划；两阶段题进一步考察新增信息后的判断更新。','',
           '20题从79道公开原题中按任务类型、学科和决策场景选取，详见[选题说明](public-subset-20.md)。','',
           '## 2. 题库怎样分布','','![题型与案例分布：推荐6题、规划10题、两阶段4题，覆盖20组案例](figures/dataset-distribution.png)','','| 范围 | 择校推荐 | 规划与决策 | 两阶段任务 | 题数 | 阶段数 |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for label,rows in [('首批20题',selected['tasks'])]:
        c=Counter(r['category'] for r in rows);lines.append(f'| {label} | {c[LABELS[0]]} | {c[LABELS[1]]} | {c[LABELS[2]]} | {len(rows)} | {sum(r["stage_count"] for r in rows)} |')
    lines+=['','首批实验包含20题，覆盖20个学生案例。图中每个实心圆代表一道题。','',
            '## 3. 如何执行和评分','','![评测流程：逐阶段发题、隔离作答、匿名独立评审、程序算分](figures/evaluation-flow.png)','','1. **组织者冻结输入。** 固定题目选择、题面与rubric版本、产品配置、预算和协议。评分材料与来源映射由组织者保管。','2. **候选Agent只接收当前阶段。** 每道题创建独立工作目录、HOME和会话；两阶段题在首次答卷完成后才释放下一阶段，在该题自身会话内继续。','3. **保留原始交付与轨迹。** 以完整 `answer.md` 为评分正文，区分最终聊天回复、工具轨迹和实际交付文件，保留失败与重试来源。','4. **分离答题与评审。** 单份匿名评审包只含对应题目、rubric和原始答卷。两阶段答卷合并按一道题评审；评审逐项给出引句、理由与待核项。','5. **代码负责算分和校验。** 根据评审记录计算分数，标注未完成和待核项。','',
            '本机使用 macOS 进程沙箱及受限网络。各产品的认证、工具和运行配置随实验记录。','',
            '## 4. 完整例题：N16-02','','![两阶段例题：新增机械项目后，正式专业仍未分流](figures/case-n16-02.png)','','**任务时点：'+case['as_of']+'。**','',
            '### 阶段 S0：先给出当前背景','', '> '+case['stages'][0]['instruction'],'',
            '保存首次答卷后，再提供第二阶段信息。','',
            '### 阶段 S1：补充经历，重新判断','', '> '+case['stages'][1]['instruction'],'',
            '### 观察点','','新增工程项目可以丰富研究适配与贡献证据，但题目再次明确“未正式分流”。评审检查Agent是否同时处理两者：利用新增信息，并保留正式专业认定和目标项目申请条件的限制。建议可以调整，也可以维持；关键是给出依据及可执行的下一步。','',
            '### 原评分项与权重','','两轮合并评分，总计100分。下表为评分项、权重和满分条件。','','| 评分项 | 分值 | 满分条件（原文） |','| --- | ---: | --- |']
    for node in rubric['nodes']:lines.append(f'| {node["label"]} | {node["points"]} | {node["full_credit"]} |')
    lines+=['','详细计分方法见[评分规则](scoring.md)。','',
            '## 5. 图表来源与复用','','- 数据：[首批20题清单](../config/selections/public-dev-20-v1.json)。','- 图片附带SVG矢量版与PNG版：可直接用于README、数据卡和演示材料。','- [图表文件记录](figures/manifest.json)保存来源与校验值。','','']
    lines += ['## 6. 换题集时如何维护', '',
              '每次实验分别保存题集、评分规则、产品配置和结果。', '',
              '本页图表对应首批20题；更换题集时，新增对应版本的图表和报告。', '',
              '重新生成SVG：', '',
              '```sh', 'python3 scripts/render_benchmark_figures.py', '```', '',
              '使用已有Pillow和中文字体，可添加 `--png --font /path/to/CJK-font.ttc` 生成PNG。', '']
    import os
    prefix = Path(os.path.relpath(figure_dir, out.parent)).as_posix()
    content = '\n'.join(lines).replace('(figures/', '('+prefix+'/')
    if not png:
        content = content.replace('.png)', '.svg)')
    out.write_text(content,encoding='utf-8')


def main():
    import sys
    sys.path.insert(0,str(ROOT))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'docs/figures/subset20-v1')
    parser.add_argument('--png',action='store_true')
    parser.add_argument('--font',type=Path)
    args=parser.parse_args()
    if args.png and not (args.font and args.font.is_file()):
        parser.error('--png needs an existing CJK font supplied with --font')
    data=load_data();args.out.mkdir(parents=True,exist_ok=True)
    font=args.font if args.png else None
    for renderer in (overview,distribution,flow,case_figure):renderer(args.out,data,font)
    guide(ROOT/'docs/benchmark-guide.md',data,args.out,args.png)
    sources=sorted(set(data[-1]+['scripts/render_benchmark_figures.py']))
    generated=[args.out/(name+ext) for name in ('benchmark-overview','dataset-distribution','evaluation-flow','case-n16-02') for ext in (('.svg','.png') if args.png else ('.svg',))]
    manifest={'schema':'benchmark-figures.1','selection_id':data[0]['id'],'task_count':len(data[0]['tasks']),'case_group_count':len(data[3]),'stage_count':sum(r['stage_count'] for r in data[0]['tasks']),
              'visual_revision':'2','contains_model_scores':False,'source_files_sha256':{n:file_hash(ROOT/n) for n in sources},
              'files':{p.name:file_hash(p) for p in generated},'guide_sha256':file_hash(ROOT/'docs/benchmark-guide.md'),
              'png_font':args.font.name if font else None,'note':'Dataset/method illustrations; not evidence of model quality or evaluation completion.'}
    (args.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'figures':len(generated),'output':str(args.out),'guide':str(ROOT/'docs/benchmark-guide.md')},ensure_ascii=False))


if __name__=='__main__':main()
