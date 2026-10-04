"""
Keyword-based stress scoring for the Stress-Relief Mailbox (English + Vietnamese).

Public API
----------
score_text(text)    -> float in [0, 42]   (DASS-21 stress-subscale scale)
analyze_text(text)  -> dict with the score AND the evidence (for debugging / tuning)
                       includes "crisis": True when a self-harm / suicide phrase
                       (un-negated) was found, so the UI can show a support message

How it works (one paragraph)
----------------------------
The text is split into clauses (at . ! ? ; , newline), each clause into word
tokens. Every position is checked against the keyword tables (longest phrase
wins). A stress keyword adds its weight (1 mild, 2 moderate, 3 strong). An
intensifier ("very", "quá", ...) within 2 tokens adds +1 to that hit (max 3).
A negator ("not", "không", ...) within 3 tokens BEFORE the hit cancels it.
Calm keywords ("happy", "vui", ...) subtract 1 each (capped); a NEGATED calm
keyword ("not happy", "không ổn") counts as +1 stress. The net points are mapped
linearly onto 0..42, reaching 42 at SATURATION_POINTS.

Vietnamese typed WITHOUT diacritics ("met moi", "ap luc") is also recognised, but
only for multi-word phrases (single ASCII words like "met" would collide with
English words such as "met").

All numbers below are UNCALIBRATED starting guesses. Tune after real use.
"""

import re
import unicodedata

SCORE_MAX = 42.0

# ---- Tunable constants -------------------------------------------------------
SATURATION_POINTS = 16.0      # net points that map to the full 42
CALM_POINTS_CAP = 3.0         # calm words can offset at most this many points
MAX_REPEATS_PER_KEYWORD = 2   # the same keyword counts at most this many times
NEGATION_WINDOW = 3           # tokens before a hit that can negate it
INTENSIFIER_WINDOW = 2        # tokens before/after a hit that can boost it
MAX_TEXT_CHARS = 5000         # longer letters are truncated
CRISIS_MIN_POINTS = 8.0       # a crisis phrase guarantees at least this many net points (= score 21, "Vừa")


# ---- Keyword tables ----------------------------------------------------------
# Entry = (phrase, weight) or (phrase, weight, ascii_ok).
#  * phrase is lowercase; a trailing * on a token means "any ending" (stress* ...)
#  * ascii_ok=True lets a SINGLE Vietnamese word also match without diacritics.
#    (multi-word Vietnamese phrases always match without diacritics)
#  * weights: 1 mild, 2 moderate, 3 strong.  Longest phrase wins at each position.
#  * CRISIS_PHRASES (bottom) are strong entries that also raise result["crisis"].
# Write "self harm", not "self-harm": hyphens split tokens.

# =============================== ENGLISH =====================================
EN_STRESS = [
    # ---- 3: strong / breakdown / hopelessness ----
    ("overwhelm*", 3), ("panic*", 3), ("burnout", 3), ("burned out", 3),
    ("burnt out", 3), ("burn out", 3), ("hopeless*", 3), ("breakdown", 3),
    ("breaking down", 3), ("falling apart", 3), ("can't cope", 3), ("cant cope", 3),
    ("cannot cope", 3), ("can't take it", 3), ("cant take it", 3),
    ("can't handle", 3), ("cant handle", 3), ("can't breathe", 3),
    ("unbearable", 3), ("freaking out", 3), ("losing it", 3), ("at my limit", 3),
    ("can't go on", 3), ("cant go on", 3), ("desperate", 3), ("terrified", 3),
    ("depress*", 3), ("devastated", 3), ("helpless", 3), ("trapped", 3),
    ("worthless", 3), ("hate myself", 3), ("hate my life", 3), ("nothing matters", 3),
    ("empty inside", 3), ("feel broken", 3), ("feeling broken", 3),
    ("feel useless", 3), ("feeling useless", 3), ("i'm useless", 3), ("im useless", 3),
    ("i'm stupid", 3), ("im stupid", 3), ("i'm a failure", 3), ("im a failure", 3),
    ("a failure", 3), ("not good enough", 3), ("never good enough", 3),
    ("not smart enough", 3), ("let everyone down", 3), ("grief", 3), ("grieving", 3),
    ("trauma*", 3), ("traumatized", 3), ("expelled", 3), ("passed away", 3),
    ("can't get out of bed", 3), ("cant get out of bed", 3),
    ("no hope", 3), ("lost all hope", 3), ("no way out", 3),

    # ---- 3: bullying / abuse / social cruelty ----
    ("bully*", 3), ("cyberbully*", 3), ("harass*", 3), ("abus*", 3),
    ("humiliat*", 3), ("made fun of", 3), ("make fun of", 3), ("making fun of", 3),
    ("laughed at me", 3), ("laugh at me", 3), ("laughing at me", 3), ("mocked", 3),
    ("mocking", 3), ("called me names", 3), ("picked on", 3), ("ganged up", 3),
    ("talk behind my back", 3), ("talking behind my back", 3),
    ("talked behind my back", 3), ("spread rumors", 3), ("spreading rumors", 3),
    ("spread rumours", 3), ("nobody likes me", 3), ("no one likes me", 3),
    ("nobody cares", 3), ("no one cares", 3), ("nobody loves me", 3),
    ("abandoned", 3), ("betrayed", 3), ("cheated on", 3), ("left me out", 3),
    ("leaves me out", 3), ("no one sits with me", 3), ("nobody sits with me", 3),
    ("eat lunch alone", 3), ("eating lunch alone", 3), ("ate lunch alone", 3),
    ("afraid to go to school", 3), ("scared to go to school", 3),
    ("hit me", 3), ("hits me", 3), ("beat me", 3), ("beats me", 3),

    # ---- 2: isolation / loneliness / not belonging ----
    ("isolated", 2), ("isolation", 2), ("lonely", 2), ("loneliness", 2),
    ("excluded", 2), ("left out", 2), ("ignored", 2), ("ignoring me", 2),
    ("ostracized", 2), ("shunned", 2), ("outcast", 2), ("outsider", 2), ("misfit", 2),
    ("rejected", 2), ("rejection", 2), ("no friends", 2), ("have no friends", 2),
    ("don't have any friends", 2), ("dont have any friends", 2),
    ("don't have friends", 2), ("dont have friends", 2), ("no real friends", 2),
    ("lost my friend", 2), ("lost my friends", 2), ("lost a friend", 2),
    ("feel alone", 2), ("feeling alone", 2), ("feel so alone", 2), ("all alone", 2),
    ("completely alone", 2), ("totally alone", 2), ("sit alone", 2), ("sat alone", 2),
    ("eating alone", 2), ("nobody understands", 2), ("no one understands", 2),
    ("nobody understands me", 2), ("no one to talk to", 2), ("nobody to talk to", 2),
    ("don't fit in", 2), ("dont fit in", 2), ("can't fit in", 2), ("cant fit in", 2),
    ("don't belong", 2), ("dont belong", 2), ("doesn't belong", 2),
    ("not invited", 2), ("didn't invite me", 2), ("didnt invite me", 2),
    ("leave me out", 2), ("unfriended", 2), ("blocked me", 2), ("ghosted", 2),
    ("ghosting", 2), ("broke up", 2), ("breakup", 2), ("break up", 2), ("dumped", 2),
    ("gossip*", 2), ("rumor*", 2), ("rumour*", 2), ("teased", 2), ("teasing", 2),
    ("insulted", 2), ("name calling", 2), ("peer pressure", 2),
    ("got in a fight", 2), ("fight with my", 2), ("fighting with my", 2),
    ("fought with my", 2), ("yelled at", 2), ("yelled at me", 2), ("screamed at", 2),
    ("shouted at", 2), ("scolded", 2), ("punished", 2), ("blamed", 2),
    ("threatened", 2), ("threats", 2),

    # ---- 2: school pressure ----
    ("bad grades", 2), ("bad grade", 2), ("low grades", 2), ("low grade", 2),
    ("held back", 2), ("failing class", 2), ("failed the", 2), ("flunk*", 2),
    ("suspended", 2), ("entrance exam", 2), ("entrance exams", 2),
    ("university entrance", 2), ("college entrance", 2), ("parents expect", 2),
    ("disappoint*", 2), ("let them down", 2), ("loser", 2), ("ugly", 2),
    ("hate school", 2), ("hate going to school", 2), ("don't want to go to school", 2),
    ("dont want to go to school", 2), ("dread school", 2),

    # ---- 2: home / loss ----
    ("divorce", 2), ("divorced", 2), ("divorcing", 2), ("family problems", 2),
    ("money problems", 2), ("parents are fighting", 2), ("fighting at home", 2),
    ("funeral", 2), ("my parents yell", 2),

    # ---- 2: feelings ----
    ("stress*", 2), ("anxi*", 2), ("on edge", 2), ("tense", 2), ("tension", 2),
    ("pressure*", 2), ("can't sleep", 2), ("cant sleep", 2), ("insomnia", 2),
    ("can't relax", 2), ("cant relax", 2), ("cannot relax", 2),
    ("unable to relax", 2), ("hard to relax", 2), ("can't calm down", 2),
    ("cant calm down", 2), ("can't focus", 2), ("cant focus", 2),
    ("can't concentrate", 2), ("cant concentrate", 2), ("dread*", 2),
    ("irritable", 2), ("irritated", 2), ("frustrat*", 2), ("exhaust*", 2),
    ("drained", 2), ("fed up", 2), ("restless", 2), ("agitated", 2), ("nervous", 2),
    ("scared", 2), ("afraid", 2), ("furious", 2), ("angry", 2), ("miserable", 2),
    ("too much", 2), ("can't stop worrying", 2), ("cant stop worrying", 2),
    ("on the verge", 2), ("struggl*", 2), ("unhappy", 2), ("heartbroken", 2),
    ("crushed", 2), ("ashamed", 2), ("shame", 2), ("embarrass*", 2), ("guilty", 2),
    ("guilt", 2), ("regret*", 2), ("insecure", 2), ("insecurity", 2),
    ("self conscious", 2), ("paranoid", 2), ("overthink*", 2), ("ruminat*", 2),
    ("uneasy", 2), ("jittery", 2), ("fear", 2), ("fears", 2), ("fearful", 2),
    ("terrible", 2), ("awful", 2), ("disaster", 2), ("sobbing", 2), ("rage", 2),
    ("livid", 2), ("resent*", 2), ("hatred", 2), ("disgusted", 2), ("numb", 2),
    ("feel numb", 2), ("feel empty", 2), ("feeling empty", 2), ("feel lost", 2),
    ("feeling lost", 2), ("powerless", 2), ("heavy heart", 2),
    ("give up", 2), ("giving up", 2), ("what's the point", 2), ("whats the point", 2),
    ("pointless", 2), ("no energy", 2), ("no motivation", 2), ("unmotivated", 2),
    ("tired all the time", 2), ("no appetite", 2), ("lost my appetite", 2),
    ("don't want to get up", 2), ("dont want to get up", 2), ("heart racing", 2),
    ("heart pounding", 2), ("chest tight", 2), ("tight chest", 2),

    # ---- 1: mild ----
    ("tired", 1), ("worr*", 1), ("upset", 1), ("sad", 1), ("feel down", 1),
    ("feeling down", 1), ("stuck", 1), ("sick of", 1), ("annoyed", 1),
    ("annoying", 1), ("hard time", 1), ("difficult", 1), ("no time", 1),
    ("not enough time", 1), ("falling behind", 1), ("fall behind", 1),
    ("behind on", 1), ("confused", 1), ("hate", 1), ("hated", 1), ("hates", 1),
    ("crying", 1), ("cry", 1), ("headache", 1), ("deadline*", 1), ("exam", 1),
    ("exams", 1), ("sleepy", 1), ("bored", 1), ("fail*", 1), ("nightmare*", 1),
    ("messed up", 1), ("hurt", 1), ("hurts", 1), ("pain", 1), ("painful", 1),
    ("jealous", 1), ("envy", 1), ("moody", 1), ("cranky", 1), ("bitter", 1),
    ("doubt*", 1), ("doubt myself", 2), ("scary", 1), ("horrible", 1), ("worst", 1),
    ("sucks", 1), ("tears", 1), ("yelling", 1), ("screaming", 1), ("stupid", 1),
    ("dumb", 1), ("idiot", 1), ("gloomy", 1), ("lazy", 1), ("procrastinat*", 1),
    ("homework", 1), ("assignment*", 1), ("midterms", 1), ("finals", 1), ("gpa", 1),
    ("low score", 1), ("bad score", 1), ("detention", 1), ("grounded", 1),
    ("compare*", 1), ("comparison", 1), ("blame", 1), ("argument*", 1),
    ("fighting with", 1), ("argued with", 1), ("shaking", 1), ("dizzy", 1),
    ("nauseous", 1), ("stomachache", 1), ("stomach ache", 1), ("so mad", 2),
]

EN_CALM = [
    "happy", "glad", "relieved", "relaxed", "peaceful", "at ease", "content",
    "grateful", "thankful", "proud", "motivated", "hopeful", "excited",
    "cheerful", "feel calm", "feeling calm", "i'm calm", "im calm", "am calm",
    "feel better", "feeling better", "feel great", "feeling great", "feel good",
    "feeling good", "feel fine", "doing fine", "doing well", "doing great",
    "all good", "looking forward", "enjoy*", "had fun", "good day", "great day",
    "made a friend", "made friends", "feel safe", "feel supported", "laughing",
    "laughed",
]

# ============================== VIETNAMESE ===================================
VI_STRESS = [
    # ---- 3: strong / breakdown / hopelessness ----
    ("kiệt sức", 3), ("kiệt quệ", 3), ("quá tải", 3), ("hoảng loạn", 3),
    ("hoảng sợ", 3), ("suy sụp", 3), ("sụp đổ", 3), ("tuyệt vọng", 3),
    ("vô vọng", 3), ("bế tắc", 3), ("không chịu nổi", 3), ("chịu hết nổi", 3),
    ("không thể chịu", 3), ("phát điên", 3), ("điên mất", 3), ("khủng hoảng", 3),
    ("ngột ngạt", 3), ("nghẹt thở", 3), ("bất lực", 3), ("không thở nổi", 3),
    ("không gánh nổi", 3), ("trầm cảm", 3), ("u uất", 3), ("uất ức", 3),
    ("chán đời", 3), ("trống rỗng", 3), ("vô dụng", 3), ("vô giá trị", 3),
    ("ghét bản thân", 3), ("ghét chính mình", 3), ("đau khổ", 3), ("khổ sở", 3),
    ("nhục nhã", 3), ("dằn vặt", 3), ("lạc lối", 3), ("mất phương hướng", 3),
    ("mất hy vọng", 3), ("không còn hy vọng", 3), ("hết hy vọng", 3),
    ("không lối thoát", 3), ("không có lối thoát", 3), ("kém cỏi", 3),
    ("không đủ giỏi", 3), ("không đủ tốt", 3), ("không xứng đáng", 3),
    ("thất vọng về bản thân", 3), ("gánh nặng", 2), ("là gánh nặng", 3),
    ("làm bố mẹ thất vọng", 3), ("làm ba mẹ thất vọng", 3),
    ("làm cha mẹ thất vọng", 3), ("làm mẹ thất vọng", 3), ("làm ba thất vọng", 3),
    ("làm bố thất vọng", 3), ("căm hận", 3), ("tương lai mù mịt", 3),
    ("không muốn làm gì", 3), ("chẳng muốn làm gì", 3), ("không muốn gặp ai", 3),
    ("qua đời", 3), ("mất người thân", 3), ("tan vỡ", 2), ("gia đình tan vỡ", 3),
    ("ở lại lớp", 3), ("lưu ban", 3), ("đuổi học", 3), ("bị đuổi học", 3),

    # ---- 3: bullying / abuse / isolation ----
    ("bắt nạt", 3), ("bị bắt nạt", 3), ("bạo lực học đường", 3), ("bị bạo lực", 3),
    ("bạo hành", 3), ("bị bạo hành", 3), ("xâm hại", 3), ("bị xâm hại", 3),
    ("quấy rối", 3), ("bị quấy rối", 3), ("bị đe dọa", 3), ("sỉ nhục", 3),
    ("bị sỉ nhục", 3), ("bị lăng mạ", 3), ("bị cô lập", 3), ("bị tẩy chay", 3),
    ("tẩy chay", 3), ("bị bỏ rơi", 3), ("bỏ rơi", 3), ("bị ghét", 3),
    ("bị ghét bỏ", 3), ("bị cười nhạo", 3), ("cười nhạo", 3), ("bị chế giễu", 3),
    ("chế giễu", 3), ("bị chê bai", 3), ("bị nói xấu", 3), ("nói xấu sau lưng", 3),
    ("bị trêu chọc", 3), ("bị loại khỏi nhóm", 3), ("không ai quan tâm", 3),
    ("không ai thích", 3), ("không ai thương", 3), ("không ai chơi với", 3),
    ("không ai muốn chơi với", 3), ("không có ai bên cạnh", 3),
    ("bị đánh", 3), ("bị đánh đập", 3), ("bị mẹ đánh", 3), ("bị ba đánh", 3),
    ("bị bố đánh", 3), ("bị cha đánh", 3), ("bị phản bội", 3), ("phản bội", 3),
    ("bị lừa dối", 3), ("bạn bè quay lưng", 3), ("sợ đi học", 3),
    ("bố mẹ cãi nhau", 3), ("ba mẹ cãi nhau", 3), ("cha mẹ cãi nhau", 3),
    ("bố mẹ ly hôn", 3), ("ba mẹ ly hôn", 3), ("cha mẹ ly hôn", 3),
    ("khóc một mình", 3), ("khóc cả đêm", 3), ("hoảng", 2),

    # ---- 2: isolation / not belonging ----
    ("cô lập", 2), ("xa lánh", 2), ("bị xa lánh", 2), ("lạc lõng", 2),
    ("cô đơn", 2), ("cô độc", 3), ("không có bạn", 2), ("chẳng có bạn", 2),
    ("không có bạn bè", 2), ("không bạn bè", 2), ("không ai hiểu", 2),
    ("không có ai để nói chuyện", 2), ("không có ai để tâm sự", 2),
    ("bị bỏ lại", 2), ("bị loại ra", 2), ("bị đẩy ra", 2), ("bị ngó lơ", 2),
    ("bị phớt lờ", 2), ("bị bơ", 2), ("bị chê", 2), ("tin đồn", 2), ("bị đồn", 2),
    ("bị trêu", 2), ("trêu chọc", 2), ("bị mắng", 2), ("bị la", 2), ("bị quát", 2),
    ("bị chửi", 3), ("bị mắng chửi", 3), ("bị bố mẹ mắng", 2), ("bị ba mẹ mắng", 2),
    ("bị mẹ mắng", 2), ("bị ba mắng", 2), ("bị bố mắng", 2), ("bị xúc phạm", 2),
    ("xúc phạm", 2), ("đe dọa", 2), ("bạo lực", 2), ("bị so sánh", 2),
    ("cãi nhau", 2), ("cãi vã", 2), ("cãi lộn", 2), ("chia tay", 2), ("thất tình", 2),
    ("mất bạn", 2), ("quay lưng", 2), ("lừa dối", 2), ("ly hôn", 2), ("ly dị", 2),
    ("khóc suốt", 2), ("nức nở", 2), ("thiếu tự tin", 2), ("không tự tin", 2),
    ("mất tự tin", 2), ("tự ti", 2), ("mặc cảm", 2), ("thua kém", 2),
    ("tự trách", 2), ("tự trách mình", 2), ("trách bản thân", 2), ("có lỗi", 2),
    ("tội lỗi", 2), ("xấu hổ", 2), ("nhục", 2), ("tủi thân", 2), ("tổn thương", 2),
    ("đau lòng", 2), ("đau buồn", 2), ("đau đớn", 2), ("thất bại", 2),
    ("hối hận", 2), ("ân hận", 2), ("day dứt", 2), ("ray rứt", 2), ("yếu đuối", 2),
    ("cực khổ", 2), ("khốn khổ", 2), ("khổ tâm", 2), ("khổ", 2),

    # ---- 2: school pressure ----
    ("điểm thấp", 2), ("điểm kém", 2), ("điểm xấu", 2), ("học kém", 2),
    ("học yếu", 2), ("học dốt", 3), ("tụt hạng", 2), ("tụt điểm", 2),
    ("thi rớt", 2), ("rớt môn", 2), ("rớt", 2), ("thi trượt", 2), ("trượt môn", 2),
    ("trượt đại học", 3), ("trượt", 2), ("đình chỉ", 2), ("kiểm điểm", 2),
    ("bị phạt", 2), ("thầy mắng", 2), ("cô mắng", 2), ("thầy cô mắng", 2),
    ("thi đại học", 2), ("thi tốt nghiệp", 2), ("thi thpt", 2), ("thi vào lớp 10", 2),
    ("thi cử", 2), ("kỳ vọng", 2), ("kì vọng", 2), ("học quá nhiều", 2),
    ("học cả ngày", 2), ("không muốn đi học", 2), ("không muốn đến trường", 2),
    ("ghét đi học", 2), ("chán học", 2), ("mờ mịt", 2), ("thiếu tiền", 2),
    ("gia đình khó khăn", 2), ("đám tang", 2), ("tang lễ", 2),

    # ---- 2: feelings / body ----
    ("căng thẳng", 2), ("stress*", 2), ("lo lắng", 2), ("lo âu", 2), ("lo sợ", 2),
    ("áp lực", 2), ("sức ép", 2), ("bồn chồn", 2), ("bực bội", 2), ("bực mình", 2),
    ("cáu gắt", 2), ("cáu kỉnh", 2), ("cáu", 2), ("khó chịu", 2), ("mất ngủ", 2),
    ("khó ngủ", 2), ("không ngủ được", 2), ("không thể ngủ", 2),
    ("không ngủ nổi", 2), ("ngủ không ngon", 2), ("thức trắng đêm", 2),
    ("trằn trọc", 2), ("hồi hộp", 2), ("sợ hãi", 2), ("mệt mỏi", 2),
    ("chán nản", 2), ("chán chường", 2), ("thất vọng", 2), ("tức giận", 2),
    ("giận dữ", 2), ("phẫn nộ", 2), ("điên tiết", 2), ("bực tức", 2),
    ("cạn kiệt", 2), ("khó thở", 2), ("không tập trung", 2), ("mất tập trung", 2),
    ("không thể tập trung", 2), ("không thể thư giãn", 2), ("khó thư giãn", 2),
    ("không thể nghỉ ngơi", 2), ("khó nghỉ ngơi", 2), ("không nghỉ ngơi được", 2),
    ("đau đầu", 2), ("quá nhiều", 2), ("thiếu kiên nhẫn", 2), ("dễ cáu", 2),
    ("nặng nề", 2), ("nặng lòng", 2), ("nặng trĩu", 2), ("lo sốt vó", 2),
    ("buồn bã", 2), ("buồn chán", 2), ("buồn bực", 2), ("u sầu", 2), ("ủ rũ", 2),
    ("tồi tệ", 2), ("tâm trạng tệ", 2), ("tâm trạng không tốt", 2),
    ("bất an", 2), ("bứt rứt", 2), ("bức bối", 2), ("ấm ức", 2), ("hụt hẫng", 2),
    ("hoang mang", 2), ("áp đảo", 2), ("bí bách", 2), ("ngộp thở", 2),
    ("chán ghét", 2), ("ghét bỏ", 2), ("căm ghét", 2), ("ghê tởm", 2),
    ("tê liệt", 2), ("vô cảm", 2), ("mất động lực", 2), ("không có động lực", 2),
    ("không còn động lực", 2), ("mắc kẹt", 2), ("bị mắc kẹt", 2), ("gắng gượng", 2),
    ("chịu đựng", 2), ("chán ăn", 2), ("bỏ ăn", 2), ("ăn không ngon", 2),
    ("ăn không nổi", 2), ("không muốn ăn", 2), ("không muốn dậy", 2),
    ("không muốn nói chuyện", 2), ("không muốn ra ngoài", 2),
    ("tim đập nhanh", 2), ("tim đập mạnh", 2), ("tức ngực", 2), ("nặng ngực", 2),
    ("run rẩy", 2), ("uể oải", 2), ("rã rời", 2), ("mệt rã rời", 2), ("mệt lả", 2),
    ("không có năng lượng", 2), ("không còn sức", 2),

    # ---- 1: mild ----
    ("mệt", 1), ("buồn", 1, True), ("lo", 1), ("chán", 1), ("sợ", 1),
    ("rối bời", 1), ("rối", 1), ("bực", 1), ("phiền", 1), ("nhạy cảm", 1),
    ("dễ khóc", 1), ("khóc", 1), ("trễ", 1), ("deadline*", 1), ("kỳ thi", 1),
    ("kì thi", 1), ("bài tập", 1), ("bài tập về nhà", 1), ("bài kiểm tra", 1),
    ("kiểm tra", 1), ("hạn nộp", 1), ("nhiều việc", 1), ("không có thời gian", 1),
    ("hết thời gian", 1), ("ác mộng", 1), ("tức", 1), ("nản", 1), ("ghét", 1),
    ("ghen tị", 1), ("ganh tị", 1), ("nuối tiếc", 1), ("giận", 1), ("tủi", 1),
    ("tệ", 1), ("thật tệ", 1), ("khó khăn", 1), ("điểm số", 1), ("so sánh", 1),
    ("cạnh tranh", 1), ("ôn thi", 1), ("học thêm", 1), ("thức khuya", 1),
    ("trốn học", 1), ("bối rối", 1), ("áy náy", 1), ("nước mắt", 1),
    ("đau bụng", 1), ("chóng mặt", 1), ("buồn nôn", 1), ("run tay", 1),
    ("đuối", 1), ("kém hơn", 1), ("phạt", 1), ("không có tiền", 1),
    ("mất hứng", 1), ("e ngại", 1), ("buồn rầu", 2),
]

VI_CALM = [
    ("vui", True), ("vui vẻ", False), ("hạnh phúc", False), ("thoải mái", False),
    ("bình tĩnh", False), ("yên tâm", False), ("an tâm", False),
    ("nhẹ nhõm", False), ("thanh thản", False), ("bình yên", False),
    ("ổn", False), ("khỏe", False), ("dễ chịu", False), ("hào hứng", False),
    ("phấn khởi", False), ("tự hào", False), ("biết ơn", False),
    ("hy vọng", False), ("yêu đời", False), ("cảm thấy tốt", False),
    ("được yêu thương", False), ("được quan tâm", False), ("được ủng hộ", False),
    ("an toàn", False), ("cười", False),
]

# ---- Crisis phrases ------------------------------------------------------------
# Strong entries (must ALSO appear in the tables above or below) whose presence,
# un-negated, sets result["crisis"] = True so the UI can show a support message.
# Exaggerations like "xấu hổ muốn chết" / "mệt muốn chết" will also trigger this;
# that is accepted (a gentle support line is harmless) - tune later if it annoys.
EN_CRISIS = [
    "suicidal", "want to die", "kill myself", "end my life", "end it all",
    "hurt myself", "harm myself", "cut myself", "self harm", "better off without me",
    "no reason to live", "don't want to live", "dont want to live",
    "wish i was dead", "wish i were dead", "want to disappear",
    "wish i was never born", "wish i wasn't born",
]
VI_CRISIS = [
    "muốn chết", "không muốn sống", "chán sống", "tự tử", "tự sát",
    "tự làm đau", "tự làm hại", "tự hại", "tự làm đau bản thân",
    "tự làm hại bản thân", "kết thúc cuộc đời", "kết thúc tất cả",
    "muốn biến mất", "biến mất khỏi thế giới", "không còn muốn sống",
    "sống không bằng chết", "ước gì mình chết", "ước mình chết",
    "ước gì không được sinh ra", "rạch tay", "cắt tay", "tự cắt", "nhảy lầu",
]
# crisis phrases are added to the stress tables at weight 3
EN_STRESS += [(p, 3) for p in EN_CRISIS]
VI_STRESS += [(p, 3) for p in VI_CRISIS]


EN_NEGATORS = {
    "not", "no", "never", "hardly", "barely", "without", "none",
    "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't",
    "won't", "haven't", "hasn't", "hadn't", "dont", "doesnt", "didnt", "isnt",
    "arent", "wasnt", "werent", "wont", "havent", "hasnt",
}
# NOTE: "can't"/"cannot" are deliberately NOT negators ("can't stop worrying").
VI_NEGATORS = {"không", "chẳng", "chả", "chưa", "đừng", "khong"}

EN_INTENSIFIERS = {
    "very", "so", "really", "extremely", "super", "totally", "completely",
    "incredibly", "absolutely", "too", "constantly", "always", "terribly",
    "deeply", "insanely", "seriously",
}
VI_INTENSIFIERS = {
    "rất", "quá", "cực", "vô cùng", "hết sức", "lắm", "siêu", "luôn",
    "thật sự", "suốt ngày", "cực kỳ", "kinh khủng", "khủng khiếp",
}


# ---- Text helpers ------------------------------------------------------------

_CLAUSE_SPLIT = re.compile(r"[.!?;,:\n\r…]+|\s[-–—]+\s")
_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def _strip_diacritics(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _normalize(text):
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("’", "'").replace("‘", "'")
    return text.lower()[:MAX_TEXT_CHARS]


def _tokenize(clause):
    return _TOKEN.findall(clause)


def _tok_match(pattern_tok, tok):
    if pattern_tok.endswith("*"):
        return tok.startswith(pattern_tok[:-1])
    return pattern_tok == tok


_CRISIS = {p.lower() for p in EN_CRISIS} | {p.lower() for p in VI_CRISIS}


def _compile(entries, lang, kind):
    """Turn raw table rows into uniform dicts, sorted longest phrase first."""
    out = []
    for e in entries:
        phrase, weight, ascii_ok = e[0], e[1], (e[2] if len(e) > 2 else False)
        tokens = tuple(_normalize(phrase).split())   # split(), NOT _tokenize: must keep the trailing *
        if not tokens:
            continue
        item = {
            "phrase": phrase, "tokens": tokens, "weight": weight,
            "lang": lang, "kind": kind,
            "ascii_tokens": None,
            "crisis": (kind == "stress" and _normalize(phrase) in _CRISIS),
        }
        if lang == "vi":
            stripped = tuple(_strip_diacritics(t) for t in tokens)
            if len(tokens) > 1 or ascii_ok:
                item["ascii_tokens"] = stripped
        out.append(item)
    out.sort(key=lambda it: -len(it["tokens"]))
    return out


def _build_tables():
    stress = _compile(EN_STRESS, "en", "stress") + _compile(VI_STRESS, "vi", "stress")
    calm_rows_vi = [(p, 1, ok) for (p, ok) in VI_CALM]
    calm_rows_en = [(p, 1) for p in EN_CALM]
    calm = _compile(calm_rows_en, "en", "calm") + _compile(calm_rows_vi, "vi", "calm")
    # one combined, longest-first list so "feel good" beats "good" etc.
    allk = stress + calm
    allk.sort(key=lambda it: -len(it["tokens"]))
    return allk


_KEYWORDS = _build_tables()
for _i, _kw in enumerate(_KEYWORDS):
    _kw["order"] = _i                       # longest-first order, used to pick the winner

_BY_FIRST = {}          # exact first token            -> [keywords]
_BY_FIRST_ASCII = {}    # no-diacritics first token    -> [keywords]
_WILD_FIRST = []        # keywords whose first token ends with "*"
for _kw in _KEYWORDS:
    _first = _kw["tokens"][0]
    if _first.endswith("*"):
        _WILD_FIRST.append(_kw)
    else:
        _BY_FIRST.setdefault(_first, []).append(_kw)
    if _kw["ascii_tokens"] is not None and not _kw["ascii_tokens"][0].endswith("*"):
        _BY_FIRST_ASCII.setdefault(_kw["ascii_tokens"][0], []).append(_kw)

_NEGATORS = EN_NEGATORS | VI_NEGATORS


def _multiword_set(words):
    return {tuple(w.split()) for w in words}


_INTENS_SINGLE = {w for w in (EN_INTENSIFIERS | VI_INTENSIFIERS) if " " not in w}
_INTENS_MULTI = _multiword_set(w for w in (EN_INTENSIFIERS | VI_INTENSIFIERS) if " " in w)


def _match_at(tokens, ascii_tokens, i):
    """Return the keyword dict matching at position i (longest first), or None."""
    cands = {}
    for kw in _BY_FIRST.get(tokens[i], ()):
        cands[kw["order"]] = kw
    for kw in _BY_FIRST_ASCII.get(ascii_tokens[i], ()):
        cands[kw["order"]] = kw
    for kw in _WILD_FIRST:
        cands[kw["order"]] = kw
    for order in sorted(cands):
        kw = cands[order]
        n = len(kw["tokens"])
        if i + n > len(tokens):
            continue
        if all(_tok_match(kw["tokens"][k], tokens[i + k]) for k in range(n)):
            return kw
        if kw["ascii_tokens"] is not None and all(
            _tok_match(kw["ascii_tokens"][k], ascii_tokens[i + k]) for k in range(n)
        ):
            return kw
    return None


def _has_intensifier(tokens, start, end):
    """Is there an intensifier within INTENSIFIER_WINDOW tokens around [start, end)?"""
    lo = max(0, start - INTENSIFIER_WINDOW)
    hi = min(len(tokens), end + INTENSIFIER_WINDOW)
    span = [t for idx, t in enumerate(tokens[lo:hi], start=lo) if not (start <= idx < end)]
    if any(t in _INTENS_SINGLE for t in span):
        return True
    for k in range(len(span) - 1):
        if (span[k], span[k + 1]) in _INTENS_MULTI:
            return True
    return False


def _is_negated(tokens, ascii_tokens, start):
    lo = max(0, start - NEGATION_WINDOW)
    for idx in range(lo, start):
        if tokens[idx] in _NEGATORS or ascii_tokens[idx] in _NEGATORS:
            return True
    return False


# ---- Public API ----------------------------------------------------------------

def analyze_text(text):
    """
    Score a letter and return the evidence.

    Returns dict:
      score          float 0..42 (1 decimal)
      stress_points  float
      calm_points    float (after cap)
      net_points     float
      crisis         bool - a self-harm / suicide phrase was found (not negated)
      hits           list of dicts: phrase, lang, kind, weight, final_weight,
                     negated, boosted, crisis, ignored_repeat
    """
    norm = _normalize(text)
    hits = []
    seen_count = {}
    stress_points = 0.0
    calm_raw = 0.0
    crisis = False

    for clause in _CLAUSE_SPLIT.split(norm):
        tokens = _tokenize(clause)
        if not tokens:
            continue
        ascii_tokens = [_strip_diacritics(t) for t in tokens]
        i = 0
        while i < len(tokens):
            kw = _match_at(tokens, ascii_tokens, i)
            if kw is None:
                i += 1
                continue
            n = len(kw["tokens"])
            key = (kw["kind"], kw["lang"], kw["tokens"])
            seen_count[key] = seen_count.get(key, 0) + 1
            repeated_too_often = seen_count[key] > MAX_REPEATS_PER_KEYWORD

            negated = _is_negated(tokens, ascii_tokens, i)
            boosted = (not negated) and kw["kind"] == "stress" and _has_intensifier(tokens, i, i + n)
            final = 0.0

            if not repeated_too_often:
                if kw["kind"] == "stress":
                    if not negated:
                        final = min(3, kw["weight"] + (1 if boosted else 0))
                        stress_points += final
                        if kw["crisis"]:
                            crisis = True
                else:  # calm keyword
                    if negated:
                        final = 1.0          # "not happy" counts as mild stress
                        stress_points += final
                    else:
                        calm_raw += 1.0
                        final = -1.0

            hits.append({
                "phrase": kw["phrase"], "lang": kw["lang"], "kind": kw["kind"],
                "weight": kw["weight"], "final_weight": final,
                "negated": negated, "boosted": boosted, "crisis": kw["crisis"],
                "ignored_repeat": repeated_too_often,
            })
            i += n

    calm_points = min(calm_raw, CALM_POINTS_CAP)
    net = max(0.0, stress_points - calm_points)
    if crisis:
        net = max(net, CRISIS_MIN_POINTS)
    score = SCORE_MAX * min(1.0, net / SATURATION_POINTS)
    return {
        "score": round(score, 1),
        "stress_points": stress_points,
        "calm_points": calm_points,
        "net_points": net,
        "crisis": crisis,
        "hits": hits,
    }


def score_text(text):
    """Convenience: just the 0..42 score."""
    return analyze_text(text)["score"]
