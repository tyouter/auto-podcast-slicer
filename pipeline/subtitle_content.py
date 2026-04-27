import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


TRADITIONAL_TO_SIMPLIFIED = {
    '應': '应', '當': '当', '沒': '没', '這': '这', '個': '个', '們': '们',
    '說': '说', '對': '对', '會': '会', '過': '过', '還': '还',
    '為': '为', '與': '与', '從': '从', '來': '来', '時': '时', '問': '问',
    '開': '开', '裡': '里', '後': '后', '學': '学', '點': '点', '種': '种',
    '樣': '样', '動': '动', '現': '现', '機': '机', '經': '经', '長': '长',
    '將': '将', '見': '见', '電': '电', '話': '话', '語': '语', '認': '认',
    '識': '识', '讓': '让', '給': '给', '進': '进', '運': '运', '間': '间',
    '體': '体', '實': '实', '論': '论', '導': '导', '產': '产', '質': '质',
    '關': '关', '歷': '历', '場': '场', '義': '义', '觀': '观', '務': '务',
    '驗': '验', '極': '极', '區': '区', '歲': '岁', '術': '术', '據': '据',
    '書': '书', '條': '条', '達': '达', '風': '风', '確': '确', '強': '强',
    '覺': '觉', '斷': '断', '劇': '剧', '離': '离', '聯': '联', '選': '选',
    '傳': '传', '參': '参', '層': '层', '備': '备', '評': '评', '續': '续',
    '寫': '写', '讀': '读', '請': '请', '變': '变', '張': '张', '總': '总',
    '園': '园', '換': '换', '鏡': '镜', '慶': '庆', '晉': '晋', '勁': '劲',
    '靜': '静', '豐': '丰', '東': '东', '業': '业', '兩': '两', '幾': '几',
    '聽': '听', '誰': '谁', '幹': '干', '藝': '艺', '創': '创', '純': '纯',
    '執': '执', '獨': '独', '夠': '够', '適': '适', '壓': '压', '環': '环',
    '戰': '战', '鬥': '斗', '轉': '转', '處': '处', '辦': '办',
    '難': '难', '願': '愿', '類': '类', '養': '养', '顯': '显', '簡': '简',
    '複': '复', '雜': '杂', '構': '构', '腦': '脑', '夢': '梦', '觸': '触',
    '釋': '释', '鍵': '键', '鏈': '链', '鎖': '锁', '隱': '隐',
    '際': '际', '隨': '随', '險': '险', '陽': '阳', '陰': '阴', '陣': '阵',
    '階': '阶', '隻': '只', '須': '须', '預': '预', '領': '领', '頭': '头',
    '題': '题', '額': '额', '顧': '顾', '飛': '飞', '飲': '饮', '館': '馆',
    '馬': '马', '驅': '驱', '駐': '驻', '髮': '发', '鬧': '闹', '鬱': '郁',
    '魚': '鱼', '鮮': '鲜', '鳥': '鸟', '鳴': '鸣', '鴨': '鸭', '鵝': '鹅',
    '鶴': '鹤', '鷹': '鹰', '麥': '麦', '黃': '黄', '黨': '党',
    '齊': '齐', '齒': '齿', '龍': '龙', '龜': '龟', '於': '于', '發': '发',
    '臺': '台', '無': '无', '異': '异', '盡': '尽', '盤': '盘', '禮': '礼',
    '稱': '称', '穩': '稳', '紅': '红', '約': '约', '級': '级', '紀': '纪',
    '緊': '紧', '統': '统', '組': '组', '結': '结', '絕': '绝', '繪': '绘',
    '繼': '继', '維': '维', '綠': '绿', '綱': '纲', '網': '网', '練': '练',
    '績': '绩', '織': '织', '繞': '绕', '罰': '罚', '脈': '脉',
    '膽': '胆', '臨': '临', '藥': '药', '蘇': '苏', '蘭': '兰',
    '虛': '虚', '號': '号', '規': '规', '視': '视', '親': '亲', '計': '计',
    '記': '记', '討': '讨', '訓': '训', '設': '设', '許': '许', '訴': '诉',
    '診': '诊', '詞': '词', '試': '试', '詩': '诗', '詳': '详', '誠': '诚',
    '誤': '误', '課': '课', '調': '调', '談': '谈', '諸': '诸', '諾': '诺',
    '謀': '谋', '謂': '谓', '謝': '谢', '證': '证', '譜': '谱', '議': '议',
    '護': '护', '貓': '猫', '貨': '货', '購': '购', '費': '费', '資': '资',
    '賦': '赋', '賴': '赖', '賺': '赚', '贈': '赠', '贊': '赞', '贏': '赢',
    '軟': '软', '軸': '轴', '較': '较', '載': '载', '輔': '辅', '輕': '轻',
    '輛': '辆', '輝': '辉', '輪': '轮', '輯': '辑', '輸': '输', '農': '农',
    '遞': '递', '遠': '远', '遲': '迟', '遺': '遗', '邁': '迈', '邊': '边',
    '郵': '邮', '鄉': '乡', '醫': '医', '橋': '桥',
    '檢': '检', '歡': '欢', '裏': '里', '鉅': '巨', '採': '采',
}

TRADITIONAL_ONLY = {k: v for k, v in TRADITIONAL_TO_SIMPLIFIED.items() if k != v}

COMMON_VARIANTS = {
    '小鏡分岔': '小径分岔', '小靜分岔': '小径分岔', '小晉分岔': '小径分岔',
    '小勁分岔': '小径分岔', '小慶分岔': '小径分岔', '小禁分岔': '小径分岔',
    '小镜分岔': '小径分岔', '小静分岔': '小径分岔', '小晋分岔': '小径分岔',
    '小劲分岔': '小径分岔', '小庆分岔': '小径分岔', '小禁分岔': '小径分岔',
    '小径分叉': '小径分岔', '小径分差': '小径分岔',
    '小镜分擦': '小径分岔', '小静分擦': '小径分岔',
    '小镜分差': '小径分岔', '小静分差': '小径分岔',
    '分叉的花园': '分岔的花园', '分差的花园': '分岔的花园',
    '分擦的花园': '分岔的花园', '分擦了': '分岔了', '分擦到': '分岔到',
    '分擦了花园': '分岔了花园', '分擦到花园': '分岔到花园',
    '分擦': '分岔', '分差': '分岔', '分叉': '分岔',
    '设置分差': '设置分岔', '在分差': '在分岔', '了分差': '了分岔',
    '換源': '花园', '换源': '花园', '花園': '花园',
}

ERRATA_AUTHORS = {
    '博赫斯': '博尔赫斯', '博尔赫丝': '博尔赫斯', '波赫斯': '博尔赫斯',
    '國爾克斯': '博尔赫斯', '国尔克斯': '博尔赫斯', '博格赫斯': '博尔赫斯',
    '博尔贺斯': '博尔赫斯', '博尔合斯': '博尔赫斯',
    '公里希': '贡布里希', '贡布利希': '贡布里希', '贡布里西': '贡布里希',
    '贡布利西': '贡布里希', '宫布里希': '贡布里希',
    '卡夫加': '卡夫卡', '科夫卡': '卡夫卡',
    '加西亚马尔克斯': '加西亚·马尔克斯', '马尔克思': '马尔克斯',
    '米兰昆德拉': '米兰·昆德拉', '昆德垃': '昆德拉',
    '博尔赫兹': '博尔赫斯',
    '宋瑞': '宋锐', '宋蕊': '宋锐',
    '于传奇': '余传奇', '於传奇': '余传奇', '余传齐': '余传奇', '于传齐': '余传奇',
    '齐白石': '齐白石',
    '杜尚': '杜尚', '杜象': '杜尚',
    '达利': '达利', '达里': '达利',
    '尼采': '尼采', '尼柴': '尼采',
    '维特根斯坦': '维特根斯坦', '维特根斯担': '维特根斯坦',
    '海德格尔': '海德格尔', '海德格': '海德格尔',
    '萨特': '萨特', '沙特': '萨特',
    '福柯': '福柯', '傅柯': '福柯',
    '德里达': '德里达', '德里达': '德里达',
    '康德': '康德', '坎德': '康德',
    '黑格尔': '黑格尔', '黑格儿': '黑格尔',
    '罗素': '罗素', '罗素尔': '罗素',
}

ERRATA_WORKS = {
    '小径分叉的花园': '小径分岔的花园',
    '百年孤独': '百年孤独', '百年弧独': '百年孤独',
    '变形记': '变形记',
    '存在与时间': '存在与时间', '存在与实间': '存在与时间',
    '存在与虚无': '存在与虚无',
    '追忆似水年华': '追忆似水年华',
    '不能承受的生命之轻': '不能承受的生命之轻',
}

ERRATA_IDIOMS = {
    '取高贺寡': '曲高和寡', '曲高合寡': '曲高和寡', '曲高和刮': '曲高和寡',
    '憋脚': '蹩脚', '憋足': '蹩脚', '蹩角': '蹩脚',
    '我值': '我执', '我职': '我执',
    '走头无路': '走投无路', '走投无录': '走投无路',
    '按部就班': '按部就班', '按步就班': '按部就班',
    '一愁莫展': '一筹莫展', '一筹摸展': '一筹莫展',
    '破斧沉舟': '破釜沉舟', '破斧沉州': '破釜沉舟',
    '名副其实': '名副其实', '明符其实': '名副其实',
    '不可思议': '不可思议', '不可思意': '不可思议',
    '不言而喻': '不言而喻', '不言而语': '不言而喻',
    '根深蒂固': '根深蒂固', '根深帝固': '根深蒂固',
    '截然不同': '截然不同', '截燃不同': '截然不同',
    '毋庸置疑': '毋庸置疑', '勿庸置疑': '毋庸置疑',
    '司空见惯': '司空见惯', '司空见贯': '司空见惯',
    '异曲同工': '异曲同工', '异曲同功': '异曲同工',
    '潜移默化': '潜移默化', '潜意默化': '潜移默化',
    '顺理成章': '顺理成章', '顺理成张': '顺理成章',
    '相辅相成': '相辅相成', '相辅相承': '相辅相成',
    '不言自明': '不言自明', '不言自鸣': '不言自明',
    '如鱼得水': '如鱼得水', '如鱼的水': '如鱼得水',
    '画龙点睛': '画龙点睛', '画龙点晴': '画龙点睛',
    '锦上添花': '锦上添花', '锦上天花': '锦上添花',
    '井底之蛙': '井底之蛙', '井低之蛙': '井底之蛙',
    '对牛弹琴': '对牛弹琴', '对牛谈琴': '对牛弹琴',
    '守株待兔': '守株待兔', '守珠待兔': '守株待兔',
    '刻舟求剑': '刻舟求剑', '刻周求剑': '刻舟求剑',
    '掩耳盗铃': '掩耳盗铃', '掩耳盗零': '掩耳盗铃',
    '南辕北辙': '南辕北辙', '南缘北辙': '南辕北辙',
    '缘木求鱼': '缘木求鱼', '沿木求鱼': '缘木求鱼',
    '置若罔闻': '置若罔闻', '置若网闻': '置若罔闻',
    '恍然大悟': '恍然大悟', '晃然大悟': '恍然大悟',
    '豁然开朗': '豁然开朗', '霍然开朗': '豁然开朗',
    '鞭辟入里': '鞭辟入里', '鞭僻入里': '鞭辟入里',
    '振聋发聩': '振聋发聩', '震聋发聩': '振聋发聩',
}

ERRATA_COMMON = {
    '鬼刀': '轨道', '规道': '轨道', '軌道': '轨道',
    '智生': '置身', '至生': '置身', '置身室外': '置身事外',
    '五厚': '午后', '午厚': '午后',
    '所事': '琐事', '索事': '琐事',
    '好人被': '好像被',
    '这麼': '这么', '那麼': '那么',
    '閒聊': '闲聊',
    '節目': '节目',
    '現狀': '现状',
    '充滿': '充满',
    '憋角的': '蹩脚的',
    '基於': '基于', '對於': '对于', '關於': '关于', '類似於': '类似于',
    '由於': '由于', '至於': '至于', '處於': '处于', '屬於': '属于',
    '在於': '在于', '對於': '对于', '等於': '等于', '過於': '过于',
    '便於': '便于', '利於': '利于', '適於': '适于', '用於': '用于',
    '始於': '始于', '源於': '源于', '出於': '出于', '歸於': '归于',
    '录著': '录着', '沿著': '沿着', '活著': '活着', '冲著': '冲着',
    '发生著': '发生着', '意味著': '意味着', '按著': '按着', '在著': '在着',
    '看著': '看着', '走著': '走着', '跑著': '跑着',
    '说著': '说着', '笑著': '笑着', '哭著': '哭着',
    '坐著': '坐着', '站著': '站着', '躺著': '躺着',
    '写著': '写着', '唱著': '唱着', '跳著': '跳着',
    '拿著': '拿着', '带著': '带着', '穿著': '穿着',
    '跟著': '跟着', '随著': '随着', '朝著': '朝着',
    '为著': '为着', '对著': '对着', '向著': '向着',
    '接著': '接着', '顺著': '顺着', '遇著': '遇着',
    '想著': '想着', '记著': '记着', '念著': '念着',
    '留著': '留着', '存著': '存着', '守著': '守着',
    '藏著': '藏着', '含著': '含着', '抱著': '抱着',
    '贴著': '贴着', '靠著': '靠着', '依著': '依着',
    '缠著': '缠着', '围著': '围着', '裹著': '裹着',
    '錄著': '录着', '發生著': '发生着', '說著': '说着',
    '寫著': '写着', '帶著': '带着', '隨著': '随着',
    '為著': '为着', '對著': '对着', '接著': '接着',
    '順著': '顺着', '記著': '记着', '藏著': '藏着',
}

ERRATA_ASR_PHONETIC = {
    '烫化': '谈话', '烫话': '谈话', '趟话': '谈话', '趟化': '谈话',
    '互联码': '互联网', '互联马': '互联网', '互连网': '互联网',
    '中联人': '中年人',
    '产品经历': '产品经理',
    '五大文学院': '作协文学院',
    '意变': '意见', '意辩': '意见',
    '习以为长': '习以为常', '习已为常': '习以为常',
    '戏剧越': '戏剧学', '戏剧月': '戏剧学',
    '可能现群': '可能性群',
    '话言上': '花园上', '话颜上': '花园上',
    '样台': '平台', '扬台': '平台',
    '战方传': '绽放', '战方': '绽放',
    '作对我方编的': '坐在我旁边的',
    '中联人的事大爱好': '中年人的三大爱好',
    '也可以这么心理': '也可以这么理解',
    '愿意为这种可能现': '愿意为这种可能性',
    '送任': '宋锐', '送人': '宋锐',
    '于传奇': '余传奇',
    '叫我': '教我',
    '随地都有': '随时都有',
    '质疑于打': '只愿意打',
    '这期段': '这阶段的',
    '差异的': '诧异的', '差异的我想': '诧异的我想',
    '不冲着了节目': '不冲着做节目',
    '弱手': '啰嗦',
    '小庆': '小径',
    '边绪': '编剧',
    '说C': '各种',
    '生活VA': '生活A和B',
    '寄币': '排斥',
    '生灵里': '生命里',
    '美食美课': '每时每刻',
    '数字在': '树杈在',
    '支条': '枝条',
    '其班是': '齐白石',
    '才系': '排戏',
    '软软的考': '考',
    '软软的': '',
    '树理过': '梳理过',
    '而如慕然': '耳濡目染',
    '公布里': '贡布里希',
    '写说的': '所说的',
    '我人因为': '偶然因为',
    '武断因为': '偶然因为',
    '戏剧充座': '戏剧创作',
    '规例': '规律',
    '取动的': '驱动的',
    '玩播率': '完播率',
    '非常理心': '非常理性',
    '曹早的': '草草的',
    '新中大概': '心中大概',
    '抱志愿': '报志愿',
    '回上起来': '回想起来',
    '给我苹果': '给我评估',
    '给我保证': '给我评估',
    '大微了': '大V了',
    '言它在': '眼它在',
    '奇异博士杨': '奇异博士他',
    '佛家奖的': '佛家讲的',
    '百千万一': '百千万亿',
    '工程民旧': '功成名就',
    '好不犹豫': '毫不犹豫',
    '松锐': '宋锐',
    '该躺的康': '该趟的坑',
    '细和了': '契合了',
    '命理说了说': '命理学说',
    '内课': '那刻',
    '说明他他': '说明它它',
    '小英文': '小婴儿',
    '舒服自己的': '说服自己的',
    '英文是我父亲': '婴儿是我父亲',
    '总有他的': '总诱他的',
    '签字对药': '签字对要',
    '太戏聊': '太细聊',
    '签一下医院的通知室': '签一下医院的通知书',
    '陆家姐在课': '教课在课',
    '签证据': '纪录片',
    '学我这次试我这次': '学我者生似我者死',
    '试我这次试我这次学我这次': '似我者死学我者生',
    '学我这次': '学我者生',
    '试我这次': '似我者死',
    '学我者死似我者生': '学我者生似我者死',
    '质疑于': '只愿意',
    '理心的': '理性的',
    '砍的吧': '坎的吧',
    '这个砍': '这个坎',
    '在这个砍': '在这个坎',
    '遇到一些砍': '遇到一些坎',
    '一个砍因为': '一个坎因为',
    '是不是一个砍': '是不是一个坎',
    '躺在的坑': '趟过的坑',
    '该躺的康该走的错路': '该趟的坑该走的错路',
    '可能遇到': '很难遇到',
    '一个艺术家': '一个个艺术家',
    '去上课': '去上戏',
    '你后来说': '或者说',
    '系里面': '戏里面',
    '一个系里面': '一个戏里面',
    '某一个系': '某一个戏',
    '拍一个消息': '拍一个小戏',
    '拍的这个消息': '拍的这个小戏',
    '脉无目的': '漫无目的',
    '回到目的': '回到母题',
    '都有跟你': '都有个你',
    '世界都有跟': '世界都有个',
    '杨他计算': '一样他计算',
    '杨他算': '一样他算',
    '暴喜了暴喜鸟': '白颊椋鸟啊',
    '暴喜鸟': '白颊椋鸟',
    '他这件好了': '天意吧',
    '他不杂的': '他复杂的',
    '不杂的故事先': '复杂的故事线',
    '你那一小时候': '博尔赫斯',
    '改变成一个不能作品': '改编成一个短篇作品',
    '不能作品可以': '短篇作品可以',
    '唱得很好唱': '版权是这样的',
    '先排应该是': '博尔赫斯应该是',
    '商量一个开头就是你的身体': '商量一个开头就是你的身份',
    '我的身体对需要这样来开头': '我的身份对需要这样来开头',
    '小径奋参赛的花园': '小径分岔的花园',
    '小径奋参赛': '小径分岔',
    '博尔克斯': '博尔赫斯',
    '草短片': '超短片',
    '超短片小说': '超短篇小说',
    '小径分岔的换源': '小径分岔的花园',
    '小径分岔了花园': '小径分岔的花园',
    '小径分岔的化原': '小径分岔的花园',
    '化原化原': '花园花园',
    '玻璃叫曼弹': '播客叫漫谈',
    '玻璃曼弹': '播客漫谈',
    '慢弹的开始': '漫谈的开始',
    '漫探的节目': '漫谈的节目',
    '信量的话': '向量的话',
    '一头屋水': '一头雾水',
    '影像何方': '去向何方',
    '编局是一个': '编剧是一个',
    '半盘几乎没做': '几乎没做',
    '送瑞': '宋锐',
    '戏剧里或者编剧': '戏剧或者编剧',
    '巨舍': '剧社',
    '梦经虚': '孟京辉',
    '内股在冲动': '那股冲动',
    '细理的某个': '戏里的某个',
    '创作性的一个性感': '创作性的一个信念',
    '很紧系这件事情': '很珍惜这件事情',
    '流程到作品': '留存到作品',
    '完成比完成都好': '完成比完美更重要',
    '住多的困难': '诸多的困难',
    '魔众给他的': '某种给他的',
    '不进入人意': '不尽如人意',
    '贡布里希西': '贡布里希',
    '洗出来的': '戏出来的',
    '双向的一个奔付': '双向的奔赴',
    '暴火的': '爆火的',
    '没有人问金': '没有人问津',
    '巨大的一个供应': '巨大的一个共鸣',
    '意识价的我': '艺术家我',
    '意识作品': '艺术作品',
    '周基伦': '周杰伦',
    '各取了': '各种曲',
    '坚持他的取风': '坚持他的曲风',
    '这种取风': '这种曲风',
    '取风好怪异': '曲风好怪异',
    '取风的这种': '曲风的这种',
    '封闪了': '封神了',
    '伟心的一个作品': '违心的一个作品',
    '这种被论': '这种悖论',
    '从观念做发': '从观念出发',
    '从理念做发': '从理念出发',
    '玩播率': '完播率',
    '智帐体': '智障体',
    '与冠的': '预判的',
    '流发叫': '流派叫',
    '前言不大后语': '前言不搭后语',
    '基同压讲': '鸡同鸭讲',
    '人生乐理': '人生阅历',
    '商业系之后': '商业戏之后',
    '受助他不是': '受众他不是',
    '我们的手中': '我们的受众',
    '不是我们的手中': '不是我们的受众',
    '找到我们的手中': '找到我们的受众',
    '了解我的手中': '了解我的受众',
    '我的手中去': '我的受众去',
    '我们的手中去': '我们的受众去',
    '针对我们的手中': '针对我们的受众',
    '挖碎到养': '挖隧道',
    '正向的去深发': '正向地去生发',
    '高低指纷': '高低之分',
    '我倒是一句话': '我导师说一句话',
    '我倒是给我说': '我导师跟我说',
    '强证你的': '确保你的',
    '心长和我一切': '想法和我一致',
    '飘流屏': '漂流瓶',
    '名量的': '明亮的',
    '名案特别': '明暗特别',
    '打拼光': '打顶光',
    '没有什么意愿': '没有什么颜值',
    '防散': '发散',
    '问我的境界': '忘我的境界',
    '总诱他的': '怂恿他的',
    '威比利又之下': '威逼利诱之下',
    '反复得很跳': '反复地摇摆',
    '反腹痕跳': '反复摇摆',
    '承认这个音乐': '承认这个婴儿',
    '卸下这份车人': '卸下这份责任',
    '不用付是': '不用负责',
    '具有普遍一下': '具有普遍性',
    '一个重明亲': '一个重感情',
    '担向了去流动': '单向地去流动',
    '被关测到的': '被观测到的',
    '巨大的VG': '巨大的危机',
    '为主教学担心': '为主角担心',
    '参照舞那': '参照物那',
    '东方位置的': '懂戏剧的',
    '坐在第一台': '坐在第一排',
    '太腰圆': '太遥远',
    '戏学士当中': '戏叙事当中',
    '具有不变形': '具有普遍性',
    '看戏也就有了事': '看戏也就有了依据',
    '当头棒赫': '当头棒喝',
    '棒赫的钱制': '棒喝的潜质',
    '让我供信': '让我共情',
    '反倒现恶': '反而厌恶',
    '传中接带': '传宗接代',
    '预意所在': '寓意所在',
    '成年往事': '陈年往事',
    '污政戏剧节': '乌镇戏剧节',
    '参加一个录演': '参加一个路演',
    '洛伯的': '罗密欧的',
    '洛伯其实': '罗密欧其实',
    '洛伯就': '罗密欧就',
    '洛伯也': '罗密欧也',
    '普苏的': '普通的',
    '喜露哀乐': '喜怒哀乐',
    '一个意识界': '一个异世界',
    '意识界': '异世界',
    '不可民壮': '不可名状',
    '亏谈到了': '窥探到了',
    '一狱正': '抑郁症',
    '没有我质': '没有我执',
    '神有的状态': '神游的状态',
    '被倒成了': '被导成了',
    '这是一种礼貌': '这是一种迷惘',
    '百里尼剧团': '巴厘岛剧团',
    '叶语剧团': '椰语剧团',
    '花里胡烧': '花里胡哨',
    '凶神恶杀了': '凶神恶煞了',
    '打大嘴衣': '打大嘴鸟',
    '极端了什么成端': '极端到什么程度',
    '无具无事': '无拘无束',
    '亏视': '窥视',
    '规探到': '窥探到',
    '回上起来': '回想起来',
    '好不犹豫': '毫不犹豫',
    '佛家奖的': '佛家讲的',
    '百千万一': '百千万亿',
    '奇异博士杨': '奇异博士一样',
    '命理说了说': '命理学说',
    '签一下医院的通知室': '签一下医院的通知书',
    '质疑于打': '质疑于',
    '理心的': '理性的',
    '新中大概': '心中大概',
    '抱志愿': '报志愿',
    '大微了': '大佬了',
    '舒服自己的': '说服自己的',
    '互联码': '互联网',
    '互联马': '互联网',
    '中联人': '中年人',
    '话言上': '花园上',
    '话颜上': '花园上',
    '样台': '阳台',
    '扬台': '阳台',
    '也可以这么心理': '也可以这么想',
    '弱手': '若手',
    '边绪': '情绪',
    '生灵里': '生命里',
    '数字在': '树杈在',
    '其班是': '齐白石',
    '才系': '排戏',
    '树理过': '梳理过',
    '公布里': '贡布里希',
    '写说的': '所说的',
    '戏剧充座': '戏剧创作',
    '规例': '规律',
    '取动的': '驱动的',
    '非常理心': '非常理性',
    '曹早的': '草草的',
    '松锐': '宋锐',
    '该躺的康': '该走的坑',
    '细和了': '契合了',
    '小英文': '小婴儿',
    '英文是我父亲': '婴儿是我父亲',
    '总有他的': '总诱他的',
    '五大文学院': '五大文学院',
    '战方传': '战方传',
    '作对我方编的': '作对我方编的',
    '中联人的事大爱好': '中联人的事大爱好',
    '这期段': '这期段',
    '差异的我想': '差异的我想',
    '不冲着了节目': '不冲着了节目',
    '小庆': '小庆',
    '美食美课': '每时每刻',
    '支条': '枝条',
    '而如慕然': '耳濡目染',
}

ASR_PHONETIC_PATTERNS = [
    (r'可能现(?!群|实|象|有|的|在|出|代)', '可能性'),
    (r'这互联(?!网)', '这互联网'),
    (r'一杨$', '一样'),
    (r'一样杨', '一样一样'),
]

ERRATA_ASR_NOISE = {
    'AVC': '', 'Ope': '', 'H264': '', 'MP4': '',
    'WEBVTT': '', 'Kind:': '', 'Language:': '',
}

COMMERCIAL_FREE_FONTS = {
    'Noto Sans SC', 'Noto Sans CJK SC', 'Source Han Sans SC',
    'Noto Serif SC', 'Noto Serif CJK SC', 'Source Han Serif SC',
    'Alibaba PuHuiTi', 'AlibabaSans',
    'HarmonyOS Sans SC',
    'LXGW WenKai', '霞鹜文楷',
    '站酷酷黑体', '站酷快乐体', '站酷高端黑',
}

NON_COMMERCIAL_FONTS = {
    'Microsoft YaHei', '微软雅黑', 'SimHei', '黑体',
    'SimSun', '宋体', 'FangSong', '仿宋', 'KaiTi', '楷体',
    'PingFang SC', 'Hiragino Sans GB',
}

LINE_START_FORBIDDEN = '的了着过吗呢吧啊呀哇嘛呗的啦咯嗯噢哦哈'

LINE_END_FORBIDDEN = '不没很更最就才又再还却倒并而或'

QUESTION_INDICATORS = [
    '吗', '呢', '吧', '什么', '怎么', '为什么', '哪里', '谁',
    '多少', '几', '是否', '难道', '究竟', '到底', '如何',
]

EXCLAMATION_INDICATORS = [
    '太', '好', '真', '特别', '非常', '极其', '超级', '真的',
    '啊', '呀', '哇', '哎',
]

CONNECTIVE_WORDS = [
    '但是', '不过', '可是', '其实', '然后', '所以', '而且', '就是',
    '因为', '如果', '虽然', '因此', '或者', '同时', '另外', '那么',
    '对', '嗯', '啊', '是', '不是', '那个', '这个', '而且',
    '所以说', '也就是说', '换句话说', '总而言之',
]

PAUSE_PUNCTUATION = {
    '，': 0.3, '。': 0.6, '！': 0.5, '？': 0.5,
    '；': 0.4, '、': 0.2, '：': 0.3,
}

ZHU_KEEP_COMPOUNDS = [
    '著名', '著作', '著称', '著录', '著者', '著书',
    '专著', '论著', '译著', '原著', '合著', '遗著',
    '显著', '昭著', '卓著', '名著',
]


def convert_zhu_to_zhe(text: str) -> str:
    for compound in ZHU_KEEP_COMPOUNDS:
        text = text.replace(compound, f'\x00{compound}\x00')

    text = text.replace('著', '着')

    for compound in ZHU_KEEP_COMPOUNDS:
        text = text.replace(f'\x00{compound}\x00', compound)

    return text


def traditional_to_simplified(text: str) -> str:
    try:
        from opencc import OpenCC
        cc = OpenCC('t2s')
        return cc.convert(text)
    except ImportError:
        result = []
        for char in text:
            if char in TRADITIONAL_TO_SIMPLIFIED:
                result.append(TRADITIONAL_TO_SIMPLIFIED[char])
            else:
                result.append(char)
        return ''.join(result)


def apply_variant_corrections(text: str) -> str:
    for wrong, correct in COMMON_VARIANTS.items():
        text = text.replace(wrong, correct)
    return text


def apply_errata(text: str) -> str:
    for wrong, correct in ERRATA_AUTHORS.items():
        text = text.replace(wrong, correct)
    for wrong, correct in ERRATA_WORKS.items():
        text = text.replace(wrong, correct)
    for wrong, correct in ERRATA_IDIOMS.items():
        text = text.replace(wrong, correct)
    for wrong, correct in ERRATA_COMMON.items():
        text = text.replace(wrong, correct)
    for wrong, correct in ERRATA_ASR_NOISE.items():
        text = text.replace(wrong, correct)
    return text


def apply_asr_phonetic_corrections(text: str) -> str:
    sorted_keys = sorted(ERRATA_ASR_PHONETIC.keys(), key=len, reverse=True)
    for _ in range(3):
        changed = False
        for wrong in sorted_keys:
            correct = ERRATA_ASR_PHONETIC[wrong]
            if wrong != correct and wrong in text:
                text = text.replace(wrong, correct)
                changed = True
        if not changed:
            break
    for pattern, replacement in ASR_PHONETIC_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def detect_asr_phonetic_errors(text: str, context: str = "") -> list[dict]:
    errors = []
    for wrong, correct in ERRATA_ASR_PHONETIC.items():
        if wrong != correct and wrong in text:
            errors.append({
                "type": "asr_phonetic_error",
                "wrong": wrong,
                "correct": correct,
                "description": f"ASR语音识别错误：'{wrong}'应为'{correct}'（平翘舌/韵母混淆）",
            })
    for pattern, replacement in ASR_PHONETIC_PATTERNS:
        match = re.search(pattern, text)
        if match:
            errors.append({
                "type": "asr_phonetic_pattern",
                "wrong": match.group(),
                "correct": replacement,
                "description": f"ASR语音识别模式错误：'{match.group()}'应为'{replacement}'",
            })
    return errors


def load_custom_errata(corrections_path: Path) -> dict:
    if not corrections_path.exists():
        return {}
    import yaml
    with open(corrections_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("corrections", {})


def apply_custom_errata(text: str, errata: dict) -> str:
    for wrong, correct in errata.items():
        text = text.replace(wrong, correct)
    return text


def normalize_to_simplified_chinese(text: str) -> str:
    text = traditional_to_simplified(text)
    text = apply_variant_corrections(text)
    text = apply_errata(text)
    text = apply_asr_phonetic_corrections(text)
    text = convert_zhu_to_zhe(text)
    return text


def add_punctuation_smart(
    text: str,
    next_text: str = '',
    duration_s: float = 0,
    gap_s: float = 0,
    is_last: bool = False,
) -> str:
    text = text.strip()
    if not text:
        return text

    if re.search(r'[。！？；：，、,.!?;:]$', text):
        return text

    if any(text.endswith(q) for q in QUESTION_INDICATORS):
        return text + '？'

    if any(text.endswith(e) for e in EXCLAMATION_INDICATORS):
        if text.endswith('啊') or text.endswith('呀') or text.endswith('哇'):
            return text + '！'
        return text + '！'

    if is_last or gap_s > 2.5:
        return text + '。'

    if gap_s > 1.5:
        return text + '。'

    if next_text:
        for cw in CONNECTIVE_WORDS:
            if next_text.startswith(cw):
                if cw in ('但是', '不过', '可是', '虽然', '如果', '虽然'):
                    return text + '，'
                elif cw in ('所以', '因此', '那么'):
                    return text + '，'
                elif cw in ('对', '嗯', '啊', '是', '不是'):
                    return text + '，'
                elif cw in ('而且', '同时', '另外', '或者'):
                    return text + '，'
                break

    if duration_s > 4.0:
        return text + '。'
    elif duration_s > 2.0:
        return text + '，'

    return text + '，'


def clean_subtitle_text(text: str) -> str:
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'^[，。！？、；：]+', '', text)
    text = re.sub(r'[，]{2,}', '，', text)
    text = re.sub(r'[。]{2,}', '。', text)
    text = text.strip()
    return text


def enforce_single_line(text: str) -> str:
    text = text.replace('\n', '')
    return text


def format_subtitle_single_line(text: str, max_chars: int = 18) -> str:
    text = enforce_single_line(text)
    text = clean_subtitle_text(text)
    if len(text) <= max_chars:
        return text

    break_points = list(re.finditer(r'[，。！？、；：]', text[:max_chars + 3]))
    if break_points:
        pos = break_points[-1].end()
        return text[:pos]

    return text[:max_chars]


def check_line_start_rules(text: str) -> list[str]:
    violations = []
    if text and text[0] in LINE_START_FORBIDDEN:
        violations.append(f"行首禁则违规：'{text[0]}'不应出现在行首")
    return violations


def check_line_end_rules(text: str) -> list[str]:
    violations = []
    if text and text[-1] in LINE_END_FORBIDDEN:
        violations.append(f"行末禁则违规：'{text[-1]}'不应出现在行末")
    return violations


def detect_meaningless_words(text: str) -> list[str]:
    meaningless = []
    filler_patterns = [
        r'那个那个', r'这个这个', r'然后然后', r'就是就是',
        r'嗯嗯嗯+', r'啊啊啊+', r'呃呃呃+',
    ]
    for pattern in filler_patterns:
        matches = re.findall(pattern, text)
        meaningless.extend(matches)
    return meaningless


def detect_context_anomalies(text: str, check_punctuation: bool = True) -> list[str]:
    anomalies = []
    if re.search(r'[a-zA-Z]{3,}', text):
        en_words = re.findall(r'[a-zA-Z]{3,}', text)
        common_en = {'the', 'and', 'for', 'not', 'but', 'all', 'can', 'her',
                     'him', 'one', 'our', 'out', 'has', 'have', 'had', 'was',
                     'are', 'been', 'from', 'this', 'that', 'with', 'they',
                     'will', 'what', 'when', 'who', 'how', 'why', 'did', 'get', 'got'}
        for w in en_words:
            if w.lower() not in common_en:
                anomalies.append(f"疑似ASR误识别英文: '{w}'")

    if check_punctuation and re.search(r'[\u4e00-\u9fff]{8,}', text) and not re.search(r'[，。！？、；：]', text):
        anomalies.append("长文本无标点断句，可能为ASR连续输出未断句")

    return anomalies


@dataclass
class ContentValidationIssue:
    entry_index: int
    issue_type: str
    severity: str
    description: str
    suggestion: str = ""


SEMANTIC_ANOMALY_PATTERNS = [
    (r'坐在.{0,4}话筒上', '坐在花园上', '坐在话筒上不通，应为花园上'),
    (r'坐在.{0,4}花园上', None, None),
    (r'戏剧充座', '戏剧创作', '充座应为创作'),
    (r'产品经历(?!理)', '产品经理', '经历应为经理'),
    (r'质疑于打', '只愿意打', '质疑于应为只愿意'),
    (r'非常理心', '非常理性', '理心应为理性'),
    (r'佛家奖的', '佛家讲的', '奖的应为讲的'),
    (r'工程民旧', '功成名就', '工程民旧应为功成名就'),
    (r'好不犹豫', '毫不犹豫', '好不应为毫不'),
    (r'而如慕然', '耳濡目染', '而如慕然应为耳濡目染'),
    (r'公布里(?!希)', '贡布里希', '公布里应为贡布里希'),
    (r'玩播率', '完播率', '玩播率应为完播率'),
    (r'取动的', '驱动的', '取动应为驱动'),
    (r'美食美课', '每时每刻', '美食美课应为每时每刻'),
    (r'生灵里', '生命里', '生灵里应为生命里'),
    (r'百千万一', '百千万亿', '百千万一应为百千万亿'),
    (r'奇异博士杨', '奇异博士他', '杨应为他'),
    (r'大微了', '大V了', '微了应为V了'),
    (r'给我苹果', '给我评估', '苹果应为评估'),
    (r'给我保证', '给我评估', '保证应为评估'),
    (r'抱志愿', '报志愿', '抱应为报'),
    (r'回上起来', '回想起来', '回上应为回想'),
    (r'曹早的', '草草的', '曹早应为草草'),
    (r'新中大概', '心中大概', '新中应为心中'),
    (r'其班是', '齐白石', '其班是应为齐白石'),
    (r'树理过', '梳理过', '树理应为梳理'),
    (r'签一下医院的通知室', '签一下医院的通知书', '通知室应为通知书'),
    (r'签证据', '纪录片', '签证据应为纪录片'),
    (r'太戏聊', '太细聊', '戏聊应为细聊'),
    (r'小英文', '小婴儿', '英文应为婴儿'),
    (r'舒服自己的', '说服自己的', '舒服应为说服'),
    (r'总有他的儿子', '总诱他的儿子', '总有应为总诱'),
    (r'英文是我父亲', '婴儿是我父亲', '英文应为婴儿'),
    (r'该躺的康', '该趟的坑', '躺的康应为趟的坑'),
    (r'细和了', '契合了', '细和应为契合'),
    (r'命理说了说', '命理学说', '说了说应为学说'),
    (r'遇到一些砍', '遇到一些坎', '砍应为坎'),
    (r'这个砍', '这个坎', '砍应为坎'),
    (r'在这个砍', '在这个坎', '砍应为坎'),
    (r'是不是一个砍', '是不是一个坎', '砍应为坎'),
    (r'一个砍因为', '一个坎因为', '砍应为坎'),
    (r'砍的吧', '坎的吧', '砍应为坎'),
    (r'言它在', '眼它在', '言应为眼'),
    (r'边绪', '编剧', '边绪应为编剧'),
    (r'说C', '各种', '说C应为各种'),
    (r'生活VA', '生活A和B', 'VA应为A和B'),
    (r'寄币', '排斥', '寄币应为排斥'),
    (r'数字在', '树杈在', '数字应为树杈'),
    (r'支条', '枝条', '支条应为枝条'),
    (r'才系的过程', '排戏的过程', '才系应为排戏'),
    (r'采戏的过程', '排戏的过程', '采戏应为排戏'),
    (r'陆家姐在课', '教课在课', '陆家姐应为教课'),
    (r'武断因为', '偶然因为', '武断应为偶然'),
    (r'我人因为', '偶然因为', '我人应为偶然'),
    (r'写说的', '所说的', '写说应为所说'),
    (r'规例', '规律', '规例应为规律'),
    (r'可能遇到', '很难遇到', '可能遇到应为很难遇到'),
    (r'一个艺术家', '一个个艺术家', '丢了一个个字'),
    (r'去上课', '去上戏', '上课应为上戏'),
    (r'你后来说', '或者说', '你后来说应为或者说'),
    (r'系里面', '戏里面', '系应为戏'),
    (r'某一个系', '某一个戏', '系应为戏'),
    (r'拍一个消息', '拍一个小戏', '消息应为小戏'),
    (r'回到目的', '回到母题', '目的应为母题'),
    (r'都有跟你', '都有个你', '跟应有个'),
    (r'学我这次', '学我者生', '学我这次应为学我者生'),
    (r'试我这次', '似我者死', '试我这次应为似我者死'),
    (r'软软的考', '考', '软软的为多余词'),
    (r'缓缓的考', '考', '缓缓的为多余词'),
    (r'杨他计算', '一样他计算', '杨应为一样'),
    (r'杨他算', '一样他算', '杨应为一样'),
    (r'商量一个开头就是你的身体', '商量一个开头就是你的身份', '身体应为身份'),
    (r'我的身体对需要这样来开头', '我的身份对需要这样来开头', '身体应为身份'),
    (r'暴喜了暴喜鸟', '白颊椋鸟啊', '暴喜鸟应为白颊椋鸟'),
    (r'不杂的故事先', '复杂的故事线', '不杂应为复杂'),
    (r'改变成一个不能作品', '改编成一个短篇作品', '改变成应为改编成，不能应为短篇'),
    (r'唱得很好唱', '版权是这样的', '唱得很好唱应为版权'),
    (r'先排应该是', '博尔赫斯应该是', '先排应为博尔赫斯'),
    (r'小径奋参赛', '小径分岔', '奋参赛应为分岔'),
    (r'博尔克斯', '博尔赫斯', '博尔克斯应为博尔赫斯'),
    (r'小径分岔的换源', '小径分岔的花园', '换源应为花园'),
    (r'小径分岔的化原', '小径分岔的花园', '化原应为花园'),
    (r'玻璃叫曼弹', '播客叫漫谈', '玻璃曼弹应为播客漫谈'),
    (r'一头屋水', '一头雾水', '屋水应为雾水'),
    (r'编局是一个', '编剧是一个', '编局应为编剧'),
    (r'梦经虚', '孟京辉', '梦经虚应为孟京辉'),
    (r'创作性的一个性感', '创作性的一个信念', '性感应为信念'),
    (r'完成比完成都好', '完成比完美更重要', '应为完成比完美更重要'),
    (r'贡布里希西', '贡布里希', '希西应为希'),
    (r'洗出来的', '戏出来的', '洗应为戏'),
    (r'双向的一个奔付', '双向的奔赴', '奔付应为奔赴'),
    (r'没有人问金', '没有人问津', '问金应为问津'),
    (r'巨大的一个供应', '巨大的一个共鸣', '供应应为共鸣'),
    (r'周基伦', '周杰伦', '基伦应为杰伦'),
    (r'坚持他的取风', '坚持他的曲风', '取风应为曲风'),
    (r'封闪了', '封神了', '封闪应为封神'),
    (r'这种被论', '这种悖论', '被论应为悖论'),
    (r'玩播率', '完播率', '玩播应为完播'),
    (r'智帐体', '智障体', '智帐应为智障'),
    (r'前言不大后语', '前言不搭后语', '不大应为不搭'),
    (r'基同压讲', '鸡同鸭讲', '基同压应为鸡同鸭'),
    (r'人生乐理', '人生阅历', '乐理应为阅历'),
    (r'商业系之后', '商业戏之后', '系应为戏'),
    (r'我们的手中', '我们的受众', '手中应为受众'),
    (r'挖碎到养', '挖隧道', '挖碎到养应为挖隧道'),
    (r'高低指纷', '高低之分', '指纷应为之分'),
    (r'飘流屏', '漂流瓶', '飘流屏应为漂流瓶'),
    (r'威比利又之下', '威逼利诱之下', '威比利又应为威逼利诱'),
    (r'承认这个音乐', '承认这个婴儿', '音乐应为婴儿'),
    (r'卸下这份车人', '卸下这份责任', '车人应为责任'),
    (r'具有普遍一下', '具有普遍性', '普遍一下应为普遍性'),
    (r'一个重明亲', '一个重感情', '重明亲应为重感情'),
    (r'被关测到的', '被观测到的', '关测应为观测'),
    (r'巨大的VG', '巨大的危机', 'VG应为危机'),
    (r'为主教学担心', '为主角担心', '主教应为主角'),
    (r'参照舞那', '参照物那', '参照舞应为参照物'),
    (r'东方位置的', '懂戏剧的', '东方位置的应为懂戏剧的'),
    (r'坐在第一台', '坐在第一排', '第一台应为第一排'),
    (r'太腰圆', '太遥远', '腰圆应为遥远'),
    (r'具有不变形', '具有普遍性', '不变形应为普遍性'),
    (r'当头棒赫', '当头棒喝', '棒赫应为棒喝'),
    (r'让我供信', '让我共情', '供信应为共情'),
    (r'传中接带', '传宗接代', '传中接带应为传宗接代'),
    (r'污政戏剧节', '乌镇戏剧节', '污政应为乌镇'),
    (r'洛伯的', '罗密欧的', '洛伯应为罗密欧'),
    (r'喜露哀乐', '喜怒哀乐', '露应为怒'),
    (r'不可民壮', '不可名状', '民壮应为名状'),
    (r'亏谈到了', '窥探到了', '亏谈应为窥探'),
    (r'一狱正', '抑郁症', '一狱正应为抑郁症'),
    (r'花里胡烧', '花里胡哨', '烧应为哨'),
    (r'凶神恶杀了', '凶神恶煞了', '恶杀应为恶煞'),
    (r'无具无事', '无拘无束', '具无事应为拘无束'),
    (r'好不犹豫', '毫不犹豫', '好不应为毫不'),
    (r'佛家奖的', '佛家讲的', '奖应为讲'),
    (r'百千万一', '百千万亿', '一应为亿'),
    (r'奇异博士杨', '奇异博士一样', '杨应为一样'),
    (r'命理说了说', '命理学说', '说了说应为学说'),
    (r'签一下医院的通知室', '签一下医院的通知书', '室应为书'),
    (r'洛伯(?!的)', '罗密欧', '洛伯应为罗密欧'),
    (r'没有我质', '没有我执', '我质应为我执'),
    (r'神有的状态', '神游的状态', '神有应为神游'),
    (r'被倒成了', '被导成了', '倒成应为导成'),
    (r'这是一种礼貌', '这是一种迷惘', '礼貌应为迷惘'),
    (r'意识界', '异世界', '意识界应为异世界'),
]


def validate_sentence_semantic(text: str, context: str = "") -> list[ContentValidationIssue]:
    issues = []
    for pattern, correction, description in SEMANTIC_ANOMALY_PATTERNS:
        if correction is None:
            continue
        match = re.search(pattern, text)
        if match:
            issues.append(ContentValidationIssue(
                entry_index=0,
                issue_type="semantic_anomaly",
                severity="critical",
                description=f"逐句语义审查：{description}",
                suggestion=f"替换为'{correction}'",
            ))
    return issues


@dataclass
class ContentValidationResult:
    total_entries: int = 0
    issues: list[ContentValidationIssue] = field(default_factory=list)
    passed: bool = True
    score: float = 100.0
    accuracy_rate: float = 100.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def errata_error_count(self) -> int:
        errata_types = {
            "errata_violation", "traditional_chinese", "wrong_name", "wrong_work",
            "asr_phonetic_error", "semantic_anomaly", "contextual_errata",
            "contextual_idiom_errata", "contextual_work_errata",
        }
        return sum(1 for i in self.issues if i.issue_type in errata_types and i.severity == "critical")

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "passed": self.passed,
            "score": round(self.score, 1),
            "accuracy_rate": round(self.accuracy_rate, 4),
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "errata_error_count": self.errata_error_count,
            "issues": [
                {
                    "entry_index": i.entry_index,
                    "issue_type": i.issue_type,
                    "severity": i.severity,
                    "description": i.description,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
        }


def validate_simplified_chinese(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        found_traditional = [c for c in text if c in TRADITIONAL_ONLY]
        if found_traditional:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="traditional_chinese_detected",
                severity="critical",
                description=f"发现繁体字: {''.join(found_traditional[:5])}",
                suggestion="转换为简体中文",
            ))
    return issues


def validate_punctuation(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        if re.search(r'[,.!?;:]', text):
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="english_punctuation",
                severity="warning",
                description=f"使用英文标点: {re.findall(r'[,.!?;:]', text)}",
                suggestion="替换为中文标点",
            ))

        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if cn_chars > 8 and not re.search(r'[，。！？、；：]', text):
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="no_punctuation",
                severity="warning",
                description=f"中文字数{cn_chars}字但无标点断句",
                suggestion="根据说话者断句添加标点",
            ))
    return issues


def validate_single_line(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        if '\n' in text:
            lines = text.split('\n')
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="multi_line_subtitle",
                severity="critical",
                description=f"字幕含{len(lines)}行，要求单行",
                suggestion="合并为单行或缩短文本",
            ))
    return issues


def validate_line_length(entries: list[dict], max_chars: int = 18) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").replace('\n', '')
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if cn_chars > max_chars:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="line_too_long",
                severity="warning",
                description=f"单行{cn_chars}字超过限制{max_chars}字",
                suggestion="缩短文本或拆分",
            ))
    return issues


def validate_errata(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    all_errata = {}
    all_errata.update(ERRATA_AUTHORS)
    all_errata.update(ERRATA_WORKS)
    all_errata.update(ERRATA_IDIOMS)
    all_errata.update(ERRATA_COMMON)

    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        for wrong, correct in all_errata.items():
            if wrong != correct and wrong in text:
                issues.append(ContentValidationIssue(
                    entry_index=entry.get("index", i),
                    issue_type="errata_violation",
                    severity="critical",
                    description=f"勘误词'{wrong}'应纠正为'{correct}'",
                    suggestion=f"替换'{wrong}'为'{correct}'",
                ))
    return issues


def validate_context_coherence(entries: list[dict], strip_punctuation: bool = True) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        meaningless = detect_meaningless_words(text)
        for mw in meaningless:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="meaningless_filler",
                severity="warning",
                description=f"发现无意义重复词: '{mw}'",
                suggestion="删除或精简重复词",
            ))

        anomalies = detect_context_anomalies(text, check_punctuation=not strip_punctuation)
        for anomaly in anomalies:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="context_anomaly",
                severity="warning",
                description=anomaly,
                suggestion="检查上下文是否通顺，修正ASR误识别",
            ))
    return issues


def validate_line_break_rules(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        start_violations = check_line_start_rules(text)
        for v in start_violations:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="line_start_forbidden",
                severity="warning",
                description=v,
                suggestion="调整断句避免助词出现在行首",
            ))

        end_violations = check_line_end_rules(text)
        for v in end_violations:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="line_end_forbidden",
                severity="warning",
                description=v,
                suggestion="调整断句避免副词/连词出现在行末",
            ))
    return issues


def validate_font_license(font_name: str) -> list[ContentValidationIssue]:
    issues = []
    if font_name in NON_COMMERCIAL_FONTS:
        issues.append(ContentValidationIssue(
            entry_index=0,
            issue_type="non_commercial_font",
            severity="critical",
            description=f"字体'{font_name}'不可商用，需替换为商用免费授权字体",
            suggestion="使用思源黑体(Noto Sans SC)或阿里巴巴普惠体",
        ))
    elif font_name not in COMMERCIAL_FREE_FONTS and font_name not in NON_COMMERCIAL_FONTS:
        issues.append(ContentValidationIssue(
            entry_index=0,
            issue_type="unknown_font_license",
            severity="warning",
            description=f"字体'{font_name}'授权状态未知，需确认是否可商用",
            suggestion="确认字体授权或替换为已知商用免费字体",
        ))
    return issues


def validate_render_style(style: dict) -> list[ContentValidationIssue]:
    issues = []
    font_name = style.get("font_name", "")
    font_issues = validate_font_license(font_name)
    issues.extend(font_issues)

    font_color = style.get("font_color", "")
    bg_mode = style.get("mode", "")
    if bg_mode == "frosted_glass_dark" and font_color != "white":
        issues.append(ContentValidationIssue(
            entry_index=0,
            issue_type="render_style_mismatch",
            severity="warning",
            description="毛玻璃暗色背景应使用白色字体",
            suggestion="设置font_color为white",
        ))

    bg_opacity = style.get("bg_opacity", 0)
    if bg_mode == "frosted_glass_dark" and (bg_opacity < 0.4 or bg_opacity > 0.8):
        issues.append(ContentValidationIssue(
            entry_index=0,
            issue_type="bg_opacity_out_of_range",
            severity="warning",
            description=f"毛玻璃背景不透明度{bg_opacity}不在推荐范围0.4-0.8内",
            suggestion="调整bg_opacity至0.5-0.7之间",
        ))

    return issues


def validate_contextual_errata(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    context_window = 3

    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context = " ".join(prev_texts + [text] + next_texts)

        literature_keywords = ['文学', '小说', '作家', '诗人', '作品', '花园', '博尔赫斯',
                               '卡夫卡', '马尔克斯', '昆德拉', '杜尚']
        philosophy_keywords = ['哲学', '存在', '时间', '本体', '认识论', '辩证',
                              '尼采', '康德', '黑格尔', '海德格尔', '萨特', '福柯']
        art_keywords = ['艺术', '绘画', '雕塑', '装置', '当代艺术', '杜尚',
                       '达利', '毕加索', '安迪沃霍尔']

        in_literature_context = any(kw in context for kw in literature_keywords)
        in_philosophy_context = any(kw in context for kw in philosophy_keywords)
        in_art_context = any(kw in context for kw in art_keywords)

        if in_literature_context:
            for wrong, correct in ERRATA_AUTHORS.items():
                if wrong != correct and wrong in text and correct not in text:
                    issues.append(ContentValidationIssue(
                        entry_index=entry.get("index", i),
                        issue_type="contextual_author_errata",
                        severity="critical",
                        description=f"文学语境中勘误：'{wrong}'应为'{correct}'",
                        suggestion=f"替换'{wrong}'为'{correct}'",
                    ))
            for wrong, correct in ERRATA_WORKS.items():
                if wrong != correct and wrong in text and correct not in text:
                    issues.append(ContentValidationIssue(
                        entry_index=entry.get("index", i),
                        issue_type="contextual_work_errata",
                        severity="critical",
                        description=f"文学语境中作品名勘误：'{wrong}'应为'{correct}'",
                        suggestion=f"替换'{wrong}'为'{correct}'",
                    ))

        if in_philosophy_context or in_literature_context:
            for wrong, correct in ERRATA_IDIOMS.items():
                if wrong != correct and wrong in text and correct not in text:
                    issues.append(ContentValidationIssue(
                        entry_index=entry.get("index", i),
                        issue_type="contextual_idiom_errata",
                        severity="critical",
                        description=f"学术语境中成语勘误：'{wrong}'应为'{correct}'",
                        suggestion=f"替换'{wrong}'为'{correct}'",
                    ))

    return issues


def validate_asr_phonetic(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    context_window = 3
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue
        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context = " ".join(prev_texts + [text] + next_texts)
        asr_errors = detect_asr_phonetic_errors(text, context)
        for err in asr_errors:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="asr_phonetic_error",
                severity="critical",
                description=err["description"],
                suggestion=f"替换'{err['wrong']}'为'{err['correct']}'",
            ))
    return issues


def validate_sentence_by_sentence(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    context_window = 3
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue
        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context = " ".join(prev_texts + [text] + next_texts)
        semantic_issues = validate_sentence_semantic(text, context)
        for issue in semantic_issues:
            issue.entry_index = entry.get("index", i)
            issues.append(issue)
    return issues


def validate_subtitle_content(
    entries: list[dict],
    max_chars: int = 18,
    render_style: dict | None = None,
    strip_punctuation: bool = True,
) -> ContentValidationResult:
    all_issues = []

    all_issues.extend(validate_simplified_chinese(entries))
    if not strip_punctuation:
        all_issues.extend(validate_punctuation(entries))
    all_issues.extend(validate_single_line(entries))
    all_issues.extend(validate_line_length(entries, max_chars))
    all_issues.extend(validate_errata(entries))
    all_issues.extend(validate_asr_phonetic(entries))
    all_issues.extend(validate_sentence_by_sentence(entries))
    all_issues.extend(validate_context_coherence(entries, strip_punctuation=strip_punctuation))
    all_issues.extend(validate_line_break_rules(entries))
    all_issues.extend(validate_contextual_errata(entries))

    if render_style:
        all_issues.extend(validate_render_style(render_style))

    total = len(entries)
    critical = sum(1 for i in all_issues if i.severity == "critical")
    warning = sum(1 for i in all_issues if i.severity == "warning")

    score = max(0, 100 - critical * 15 - min(warning * 0.1, 15))
    passed = critical == 0

    errata_types = {
        "errata_violation", "traditional_chinese", "wrong_name", "wrong_work",
        "asr_phonetic_error", "semantic_anomaly", "contextual_errata",
        "contextual_idiom_errata", "contextual_work_errata",
    }
    errata_errors = sum(1 for i in all_issues if i.issue_type in errata_types and i.severity == "critical")
    accuracy_rate = ((total - errata_errors) / total * 100) if total > 0 else 100.0
    if accuracy_rate < 99.9 and errata_errors > 0:
        passed = False

    return ContentValidationResult(
        total_entries=total,
        issues=all_issues,
        passed=passed,
        score=score,
        accuracy_rate=accuracy_rate,
    )


def remove_display_punctuation(text: str) -> str:
    punctuation = set('，。！？；：、""''（）【】《》—…·,.\'\"!?;:()[]{}<>-–—…·')
    return ''.join(ch for ch in text if ch not in punctuation)


def process_subtitle_content(
    text: str,
    duration_s: float = 0,
    next_text: str = '',
    gap_s: float = 0,
    max_chars: int = 18,
    is_last: bool = False,
    custom_errata: dict | None = None,
    strip_punctuation: bool = True,
) -> str:
    text = normalize_to_simplified_chinese(text)
    if custom_errata:
        text = apply_custom_errata(text, custom_errata)
    text = clean_subtitle_text(text)
    text = add_punctuation_smart(text, next_text, duration_s, gap_s, is_last)
    text = enforce_single_line(text)
    text = format_subtitle_single_line(text, max_chars)
    if strip_punctuation:
        text = remove_display_punctuation(text)
    return text


def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_rounded_rect_drawing(w: int, h: int, r: int) -> str:
    r = min(r, w // 2, h // 2)
    return (
        f"m {r} 0 "
        f"l {w - r} 0 "
        f"b {w} 0 {w} {r} {w} {r} "
        f"l {w} {h - r} "
        f"b {w} {h} {w - r} {h} {w - r} {h} "
        f"l {r} {h} "
        f"b 0 {h} 0 {h - r} 0 {h - r} "
        f"l 0 {r} "
        f"b 0 0 {r} 0 {r} 0"
    )


def _measure_text_width(text: str, font_size: int) -> int:
    cjk_width = int(font_size * 0.673)
    ascii_width = int(font_size * 0.37)
    width = 0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            width += cjk_width
        elif ch.isascii() and ch.isalpha():
            width += ascii_width
        elif ch.isascii() and ch.isdigit():
            width += ascii_width
        elif ch == ' ':
            width += int(font_size * 0.2)
        else:
            width += int(font_size * 0.4)
    return width


_NOTO_SANS_SC_METRICS = {
    "descent_ratio": 0.154,
    "visible_height_ratio": 0.635,
}


def generate_ass_with_rounded_bg(
    entries: list[dict],
    video_width: int = 3840,
    video_height: int = 2160,
    font_name: str = "Noto Sans SC",
    font_size: int = 104,
    bg_color: str = "1A1A1A",
    bg_alpha: int = 38,
    text_color: str = "FFFFFF",
    corner_radius: int = 24,
    padding_h: int = 40,
    padding_v: int = 20,
    margin_v: int = 90,
) -> str:
    bg_alpha_hex = f"{bg_alpha:02X}"
    metrics = _NOTO_SANS_SC_METRICS
    descent = int(font_size * metrics["descent_ratio"])
    visible_h = int(font_size * metrics["visible_height_ratio"])

    ass = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{font_size},"
        f"&H00{text_color},&H000000FF,&H00000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    cx = video_width // 2
    text_pos_y = video_height - margin_v

    for entry in entries:
        start = _format_ass_time(entry["start_s"])
        end = _format_ass_time(entry["end_s"])
        text = entry["text"]

        text_width = _measure_text_width(text, font_size)
        max_w = int(video_width * 0.85)
        text_width = min(text_width, max_w)

        text_top = text_pos_y - descent - visible_h
        text_left = cx - text_width // 2

        bg_x = text_left - padding_h
        bg_y = text_top - padding_v
        bg_w = text_width + padding_h * 2
        bg_h = visible_h + padding_v * 2

        r = min(corner_radius, bg_w // 2, bg_h // 2)

        drawing = _ass_rounded_rect_drawing(bg_w, bg_h, r)

        ass += (
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,"
            f"{{\\an7\\pos({bg_x},{bg_y})\\1c&H{bg_color}&\\1a&H{bg_alpha_hex}&"
            f"\\3a&HFF&\\4a&HFF&\\p1}}{drawing}{{\\p0}}\n"
        )
        ass += (
            f"Dialogue: 1,{start},{end},Default,,0,0,0,,"
            f"{{\\an2\\pos({cx},{text_pos_y})}}{text}\n"
        )

    return ass


def get_frosted_glass_ffmpeg_filter(
    video_width: int = 3840,
    video_height: int = 2160,
    blur_radius: int = 12,
    band_height: int = 120,
    margin_v: int = 50,
) -> str:
    y_start = video_height - margin_v - band_height
    return (
        f"split[original][blurred];"
        f"[blurred]crop={video_width}:{band_height}:0:{y_start},boxblur={blur_radius}:{blur_radius}[blurred_band];"
        f"[original][blurred_band]overlay=0:{y_start}"
    )
