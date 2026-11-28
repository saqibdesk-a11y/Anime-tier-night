/* How to play, in English, Arabic, Urdu and Hindi. Every game shows the same button:
   HowTo.button("lantern") returns its HTML, and tapping it opens a sheet with a language switch.
   English is the default; the language you pick is remembered for every game.
   Button names stay in English inside the other languages ("Lock in"), because the game screens
   themselves are in English and players need to find those words.
   Content: a line starting with "#" is a heading; every other line is one point. */
(function(){
  const LANGS = [
    {id:"en", name:"English", dir:"ltr"},
    {id:"ar", name:"العربية", dir:"rtl", font:"Noto+Naskh+Arabic:wght@400;700", family:"'Noto Naskh Arabic'"},
    {id:"ur", name:"اردو", dir:"rtl", font:"Noto+Nastaliq+Urdu:wght@400;700", family:"'Noto Nastaliq Urdu'"},
    {id:"hi", name:"हिन्दी", dir:"ltr", font:"Noto+Sans+Devanagari:wght@400;700", family:"'Noto Sans Devanagari'"},
  ];
  const UI = {
    en:{title:"How to play", close:"Close"},
    ar:{title:"طريقة اللعب", close:"إغلاق"},
    ur:{title:"کھیلنے کا طریقہ", close:"بند کریں"},
    hi:{title:"कैसे खेलें", close:"बंद करें"},
  };

  const T = {};

  /* ---------- Tier List Night ---------- */
  T.tierlist = {
    en:`Everyone ranks the same list: anime, characters, food, anything.
The list comes one of three ways: everyone secretly adds a few favourites, the host types it, or the AI picks it.
Put each poster in a tier. <b>S</b> is the best, then <b>A</b>, <b>B</b>, <b>C</b>, <b>D</b>, and <b>F</b> at the bottom.
On a phone, tap a poster, then tap a tier letter. On a computer, drag it.
Tap <b>"I'm done ranking"</b> when you're happy. The round also ends when the timer runs out.
Then everyone's boards are revealed one by one, with the group's verdict, and the AI roasts everyone's taste.`,
    ar:`يرتّب الجميع نفس القائمة: أنمي، شخصيات، طعام، أو أي شيء.
تأتي القائمة بإحدى ثلاث طرق: كل لاعب يضيف مفضّلاته سرًّا، أو يكتبها المضيف، أو يختارها الذكاء الاصطناعي.
ضع كل صورة في مستوى. <b>S</b> هو الأفضل، ثم <b>A</b> و<b>B</b> و<b>C</b> و<b>D</b>، و<b>F</b> في الأسفل.
على الهاتف: اضغط على الصورة ثم على حرف المستوى. على الكمبيوتر: اسحبها.
اضغط <b>"I'm done ranking"</b> عندما تنتهي. تنتهي الجولة أيضًا عندما ينتهي الوقت.
بعدها تُكشف لوحات الجميع واحدة تلو الأخرى مع رأي المجموعة، ويسخر الذكاء الاصطناعي من ذوق الجميع.`,
    ur:`سب لوگ ایک ہی فہرست کو رینک کرتے ہیں: اینیمے، کردار، کھانے، کچھ بھی۔
فہرست تین طریقوں سے بنتی ہے: ہر کوئی چپکے سے اپنی پسند کی چیزیں ڈالتا ہے، یا ہوسٹ خود لکھتا ہے، یا AI چنتا ہے۔
ہر تصویر کو ایک درجے میں رکھیں۔ <b>S</b> سب سے بہترین، پھر <b>A</b>، <b>B</b>، <b>C</b>، <b>D</b>، اور <b>F</b> سب سے نیچے۔
فون پر: تصویر پر ٹیپ کریں، پھر درجے کے حرف پر ٹیپ کریں۔ کمپیوٹر پر: کھینچ کر رکھیں۔
جب تسلی ہو جائے تو <b>"I'm done ranking"</b> دبائیں۔ وقت ختم ہونے پر بھی راؤنڈ ختم ہو جاتا ہے۔
پھر سب کے بورڈ ایک ایک کر کے دکھائے جاتے ہیں، گروپ کا فیصلہ آتا ہے، اور AI سب کی پسند کا مذاق اڑاتا ہے۔`,
    hi:`सब लोग एक ही लिस्ट को रैंक करते हैं: एनीमे, किरदार, खाना, कुछ भी।
लिस्ट तीन तरीक़ों से बनती है: हर कोई चुपके से अपनी पसंद जोड़ता है, या होस्ट ख़ुद लिखता है, या AI चुनता है।
हर तस्वीर को एक लेवल में रखें। <b>S</b> सबसे अच्छा, फिर <b>A</b>, <b>B</b>, <b>C</b>, <b>D</b>, और <b>F</b> सबसे नीचे।
फ़ोन पर: तस्वीर पर टैप करें, फिर लेवल के अक्षर पर टैप करें। कंप्यूटर पर: खींचकर रखें।
जब ठीक लगे तो <b>"I'm done ranking"</b> दबाएँ। टाइमर ख़त्म होने पर भी राउंड ख़त्म हो जाता है।
फिर सबके बोर्ड एक-एक करके दिखाए जाते हैं, ग्रुप का फ़ैसला आता है, और AI सबकी पसंद का मज़ाक़ उड़ाता है।`,
  };

  /* ---------- Imposter ---------- */
  T.imposter = {
    en:`Everyone gets a secret word, except the imposter.
<b>Undercover</b> mode: the imposter gets a similar word and doesn't know they're the imposter. <b>Clueless</b> mode: the imposter knows, and only sees the category.
Take turns giving one short clue about your word. Not too easy, or the imposter works out the word.
Then talk it out and vote for who you think the imposter is.
If the imposter is caught, they get one last guess at the real word.
A hint gave the word away? Tap <b>"Too obvious"</b> on it. If half the table flags it, its giver loses 1 point.
# Special roles (sometimes in play)
<b>Jester:</b> wants to get voted out. Vote them out and you lose a point.
<b>Detective:</b> after the clues, can secretly check one player.
<b>Accomplice:</b> knows the imposter and helps them escape.
<b>Lovers:</b> two crew players who know each other.
# Points
Vote for the imposter: +2. Imposter escapes: +3, or +4 if an innocent was voted out. Caught imposter guesses the word: +3. Jester voted out: +5 for the Jester.
Most points after all the rounds wins.`,
    ar:`كل لاعب يحصل على كلمة سرّية، إلا المحتال.
وضع <b>Undercover</b>: يحصل المحتال على كلمة قريبة ولا يعرف أنه المحتال. وضع <b>Clueless</b>: المحتال يعرف ذلك، ويرى الفئة فقط.
بالدور، يعطي كل لاعب تلميحًا قصيرًا عن كلمته. لا تجعله سهلًا جدًا، وإلا سيعرف المحتال الكلمة.
بعدها تناقشوا وصوّتوا على من تظنّونه المحتال.
إذا انكشف المحتال، يحصل على محاولة أخيرة لتخمين الكلمة الحقيقية.
تلميح كشف الكلمة؟ اضغط <b>"Too obvious"</b> عليه. إذا أشار إليه نصف اللاعبين، يخسر صاحبه نقطة.
# أدوار خاصة (تظهر أحيانًا)
<b>المهرّج (Jester):</b> يريد أن يُطرد بالتصويت. إذا صوّتّ ضده تخسر نقطة.
<b>المحقّق (Detective):</b> بعد التلميحات، يكشف سرًّا حقيقة لاعب واحد.
<b>الشريك (Accomplice):</b> يعرف المحتال ويساعده على الهروب.
<b>العاشقان (Lovers):</b> لاعبان من الفريق يعرفان بعضهما.
# النقاط
التصويت ضد المحتال: ‎+2. هروب المحتال: ‎+3، أو ‎+4 إذا طُرد بريء. المحتال المكشوف يخمّن الكلمة: ‎+3. طرد المهرّج: ‎+5 للمهرّج.
صاحب أعلى النقاط بعد كل الجولات يفوز.`,
    ur:`سب کو ایک خفیہ لفظ ملتا ہے، سوائے امپوسٹر کے۔
<b>Undercover</b> موڈ: امپوسٹر کو ملتا جلتا لفظ ملتا ہے اور اسے پتا نہیں ہوتا کہ وہ امپوسٹر ہے۔ <b>Clueless</b> موڈ: امپوسٹر کو پتا ہوتا ہے، اور اسے صرف کیٹیگری نظر آتی ہے۔
باری باری اپنے لفظ کے بارے میں ایک چھوٹا سا اشارہ دیں۔ بہت آسان نہیں، ورنہ امپوسٹر لفظ سمجھ جائے گا۔
پھر بحث کریں اور اسے ووٹ دیں جو آپ کے خیال میں امپوسٹر ہے۔
اگر امپوسٹر پکڑا جائے تو اسے اصل لفظ بوجھنے کا ایک آخری موقع ملتا ہے۔
کسی اشارے نے لفظ بتا دیا؟ اس پر <b>"Too obvious"</b> دبائیں۔ اگر آدھے کھلاڑی نشان لگائیں تو دینے والے کا 1 پوائنٹ کٹ جاتا ہے۔
# خاص کردار (کبھی کبھی آتے ہیں)
<b>جوکر (Jester):</b> چاہتا ہے کہ اسے ووٹ سے نکالا جائے۔ آپ نے اسے نکالا تو آپ کا ایک پوائنٹ کٹے گا۔
<b>جاسوس (Detective):</b> اشاروں کے بعد چپکے سے ایک کھلاڑی کو چیک کر سکتا ہے۔
<b>ساتھی (Accomplice):</b> امپوسٹر کو جانتا ہے اور اسے بچنے میں مدد دیتا ہے۔
<b>عاشق (Lovers):</b> ٹیم کے دو کھلاڑی جو ایک دوسرے کو جانتے ہیں۔
# پوائنٹس
امپوسٹر کو ووٹ: ‎+2۔ امپوسٹر بچ جائے: ‎+3، اور اگر کوئی بےقصور نکالا گیا تو ‎+4۔ پکڑا گیا امپوسٹر لفظ بوجھ لے: ‎+3۔ جوکر نکالا جائے: جوکر کو ‎+5۔
سارے راؤنڈز کے بعد سب سے زیادہ پوائنٹس والا جیتتا ہے۔`,
    hi:`सबको एक गुप्त शब्द मिलता है, सिवाय इम्पोस्टर के।
<b>Undercover</b> मोड: इम्पोस्टर को मिलता-जुलता शब्द मिलता है और उसे पता नहीं होता कि वह इम्पोस्टर है। <b>Clueless</b> मोड: इम्पोस्टर को पता होता है, और उसे सिर्फ़ कैटेगरी दिखती है।
बारी-बारी से अपने शब्द के बारे में एक छोटा सा इशारा दें। बहुत आसान नहीं, वरना इम्पोस्टर शब्द समझ जाएगा।
फिर बहस करें और उसे वोट दें जो आपको इम्पोस्टर लगता है।
अगर इम्पोस्टर पकड़ा गया, तो उसे असली शब्द बूझने का एक आख़िरी मौक़ा मिलता है।
किसी इशारे ने शब्द बता दिया? उस पर <b>"Too obvious"</b> दबाएँ। अगर आधे खिलाड़ी फ़्लैग करें, तो देने वाले का 1 पॉइंट कटता है।
# ख़ास किरदार (कभी-कभी आते हैं)
<b>जोकर (Jester):</b> चाहता है कि उसे वोट से निकाला जाए। आपने उसे निकाला तो आपका एक पॉइंट कटेगा।
<b>जासूस (Detective):</b> इशारों के बाद चुपके से एक खिलाड़ी को चेक कर सकता है।
<b>साथी (Accomplice):</b> इम्पोस्टर को जानता है और उसे बचने में मदद करता है।
<b>प्रेमी (Lovers):</b> टीम के दो खिलाड़ी जो एक-दूसरे को जानते हैं।
# पॉइंट्स
इम्पोस्टर को वोट: +2। इम्पोस्टर बच जाए: +3, और अगर कोई बेक़सूर निकाला गया तो +4। पकड़ा गया इम्पोस्टर शब्द बूझ ले: +3। जोकर निकाला जाए: जोकर को +5।
सारे राउंड के बाद सबसे ज़्यादा पॉइंट्स वाला जीतता है।`,
  };

  /* ---------- Codenames ---------- */
  T.codenames = {
    en:`Two teams. Each team has one <b>spymaster</b>; everyone else guesses.
The board has 25 word cards. Only the spymasters see which cards are their team's agents, which are bystanders, and which one is the <b>assassin</b>.
On your turn, your spymaster gives <b>one word and a number</b>, like <b>OCEAN 2</b>: "two of our cards are linked to ocean". The word can't be on the board.
Guessers tap a card to mark it, then press <b>"Lock in"</b> to reveal it.
Your team's agent: keep guessing, up to the number plus one. A bystander or the other team's agent: your turn ends.
The assassin: your team loses on the spot.
The first team to find all its agents wins.`,
    ar:`فريقان. لكل فريق <b>قائد جواسيس</b> (spymaster)، والباقون يخمّنون.
على اللوحة 25 بطاقة كلمات. القادة فقط يرون أيّ البطاقات عملاء فريقهم، وأيّها محايدة، وأيّها <b>القاتل</b> (assassin).
في دوركم، يعطي القائد <b>كلمة واحدة ورقمًا</b>، مثل <b>بحر 2</b>: أي أن بطاقتين لنا مرتبطتان بالبحر. لا يجوز أن تكون الكلمة على اللوحة.
اضغط على بطاقة لتضع عليها علامة، ثم اضغط <b>"Lock in"</b> لكشفها.
عميل لفريقك: استمر في التخمين، حتى الرقم زائد واحد. بطاقة محايدة أو عميل للفريق الآخر: ينتهي دوركم.
القاتل: يخسر فريقك فورًا.
أول فريق يجد كل عملائه يفوز.`,
    ur:`دو ٹیمیں۔ ہر ٹیم کا ایک <b>اسپائی ماسٹر</b> ہوتا ہے، باقی سب اندازہ لگاتے ہیں۔
بورڈ پر 25 لفظوں والے کارڈ ہوتے ہیں۔ صرف اسپائی ماسٹر دیکھ سکتے ہیں کہ کون سے کارڈ اپنی ٹیم کے ایجنٹ ہیں، کون سے عام لوگ ہیں، اور کون سا <b>قاتل</b> (assassin) ہے۔
آپ کی باری پر اسپائی ماسٹر <b>ایک لفظ اور ایک نمبر</b> دیتا ہے، جیسے <b>سمندر 2</b>: یعنی ہمارے دو کارڈ سمندر سے جڑے ہیں۔ یہ لفظ بورڈ پر نہیں ہو سکتا۔
کارڈ پر ٹیپ کر کے نشان لگائیں، پھر <b>"Lock in"</b> دبا کر اسے کھولیں۔
اپنی ٹیم کا ایجنٹ نکلا: اندازہ لگاتے رہیں، نمبر سے ایک زیادہ تک۔ عام آدمی یا دوسری ٹیم کا ایجنٹ: آپ کی باری ختم۔
قاتل نکلا: آپ کی ٹیم فوراً ہار جاتی ہے۔
جو ٹیم پہلے اپنے سارے ایجنٹ ڈھونڈ لے، وہ جیتتی ہے۔`,
    hi:`दो टीमें। हर टीम का एक <b>स्पाईमास्टर</b> होता है, बाक़ी सब अंदाज़ा लगाते हैं।
बोर्ड पर 25 शब्दों वाले कार्ड होते हैं। सिर्फ़ स्पाईमास्टर देख सकते हैं कि कौन से कार्ड अपनी टीम के एजेंट हैं, कौन से आम लोग हैं, और कौन सा <b>क़ातिल</b> (assassin) है।
आपकी बारी पर स्पाईमास्टर <b>एक शब्द और एक नंबर</b> देता है, जैसे <b>समुद्र 2</b>: यानी हमारे दो कार्ड समुद्र से जुड़े हैं। यह शब्द बोर्ड पर नहीं हो सकता।
कार्ड पर टैप करके निशान लगाएँ, फिर <b>"Lock in"</b> दबाकर उसे खोलें।
अपनी टीम का एजेंट निकला: अंदाज़ा लगाते रहें, नंबर से एक ज़्यादा तक। आम आदमी या दूसरी टीम का एजेंट: आपकी बारी ख़त्म।
क़ातिल निकला: आपकी टीम तुरंत हार जाती है।
जो टीम पहले अपने सारे एजेंट ढूँढ ले, वह जीतती है।`,
  };

  /* ---------- Werewolf ---------- */
  T.werewolf = {
    en:`Everyone gets a secret role card. Most players are on the <b>Good</b> team, the village. A few are werewolves on the <b>Evil</b> team.
<b>Night:</b> the werewolves choose someone to eliminate. Some Good roles use their powers in secret.
<b>Day:</b> everyone sees who was eliminated, talks it out, and votes someone out.
Good wins when every evil player is gone. Evil wins when there are as many of them as good players.
The game runs itself. Just follow your screen.
# Roles
<b>Werewolf:</b> each night, picks someone to eliminate with the other wolves. By day, blends in.
<b>Alpha Wolf:</b> leads the wolves. Looks Good to the Seer.
<b>Wolf Shaman:</b> once per game, by day, saves another evil player from the vote.
<b>Siren:</b> evil. If voted out, every Good power fails the next night.
<b>Seer:</b> each night, learns if one player is Good or Evil.
<b>Doctor:</b> each night, protects one player from being killed. Can be yourself.
<b>Hunter:</b> if killed at night, 75% chance to take a random evil player down too.
<b>Knight:</b> survives one night attack.
<b>Mayor:</b> your vote counts twice.
<b>Assassin:</b> once per game, at night, eliminates anyone.
<b>Necromancer:</b> once per game, brings one dead Good player back to life.
<b>Jester:</b> on the Good team, but also wins if they die.
<b>Villager:</b> no powers. Find the wolves and vote them out.`,
    ar:`كل لاعب يحصل على بطاقة دور سرّية. معظم اللاعبين في فريق <b>الخير</b>، أي القرية. وقلّة منهم مستذئبون في فريق <b>الشر</b>.
<b>الليل:</b> يختار المستذئبون شخصًا لإقصائه. وبعض أدوار الخير تستخدم قدراتها سرًّا.
<b>النهار:</b> يعرف الجميع من أُقصي، يتناقشون، ثم يصوّتون لطرد أحد.
يفوز الخير عندما يختفي كل الأشرار. ويفوز الشر عندما يصبح عددهم مساويًا لعدد الأخيار.
اللعبة تدير نفسها. فقط اتبع ما يظهر على شاشتك.
# الأدوار
<b>المستذئب (Werewolf):</b> كل ليلة يختار مع الذئاب شخصًا لإقصائه. وفي النهار يتظاهر بالبراءة.
<b>الذئب القائد (Alpha Wolf):</b> يقود الذئاب. يظهر للعرّاف كأنه من الخير.
<b>شامان الذئاب (Wolf Shaman):</b> مرة واحدة في اللعبة، في النهار، ينقذ شريرًا آخر من التصويت.
<b>الحورية (Siren):</b> من الشر. إذا طُردت بالتصويت، تفشل كل قدرات الخير في الليلة التالية.
<b>العرّاف (Seer):</b> كل ليلة يعرف إن كان لاعب واحد من الخير أو الشر.
<b>الطبيب (Doctor):</b> كل ليلة يحمي لاعبًا واحدًا من القتل، ويمكن أن يحمي نفسه.
<b>الصيّاد (Hunter):</b> إذا قُتل ليلًا، فهناك احتمال 75% أن يأخذ معه شريرًا عشوائيًا.
<b>الفارس (Knight):</b> ينجو من هجوم ليلي واحد.
<b>العمدة (Mayor):</b> صوتك يُحسب مرتين.
<b>القاتل (Assassin):</b> مرة واحدة في اللعبة، ليلًا، يُقصي أي لاعب.
<b>مُحيي الموتى (Necromancer):</b> مرة واحدة في اللعبة، يعيد لاعبًا ميتًا من الخير إلى الحياة.
<b>المهرّج (Jester):</b> من فريق الخير، لكنه يفوز أيضًا إذا مات.
<b>القروي (Villager):</b> بلا قدرات. اكتشف الذئاب وصوّت لطردهم.`,
    ur:`سب کو ایک خفیہ کردار کا کارڈ ملتا ہے۔ زیادہ تر کھلاڑی <b>اچھی</b> ٹیم میں ہوتے ہیں، یعنی گاؤں۔ کچھ بھیڑیے ہوتے ہیں جو <b>بُری</b> ٹیم میں ہیں۔
<b>رات:</b> بھیڑیے کسی ایک کو ختم کرنے کے لیے چنتے ہیں۔ کچھ اچھے کردار چپکے سے اپنی طاقت استعمال کرتے ہیں۔
<b>دن:</b> سب کو پتا چلتا ہے کہ کون ختم ہوا، پھر بات چیت ہوتی ہے اور ووٹ سے کسی کو نکالا جاتا ہے۔
جب سارے بُرے کھلاڑی ختم ہو جائیں تو اچھی ٹیم جیتتی ہے۔ جب بُرے کھلاڑی اچھوں کے برابر ہو جائیں تو بُری ٹیم جیتتی ہے۔
گیم خود چلتی ہے۔ بس اپنی اسکرین دیکھتے رہیں۔
# کردار
<b>بھیڑیا (Werewolf):</b> ہر رات باقی بھیڑیوں کے ساتھ کسی کو ختم کرنے کے لیے چنتا ہے۔ دن میں معصوم بنا رہتا ہے۔
<b>سردار بھیڑیا (Alpha Wolf):</b> بھیڑیوں کا لیڈر۔ نجومی کو اچھا نظر آتا ہے۔
<b>بھیڑیوں کا جادوگر (Wolf Shaman):</b> پوری گیم میں ایک بار، دن میں، کسی دوسرے بُرے کھلاڑی کو ووٹ سے بچاتا ہے۔
<b>جل پری (Siren):</b> بُری ٹیم۔ اگر ووٹ سے نکالی گئی تو اگلی رات اچھوں کی ساری طاقتیں ناکام ہو جاتی ہیں۔
<b>نجومی (Seer):</b> ہر رات جان لیتا ہے کہ ایک کھلاڑی اچھا ہے یا بُرا۔
<b>ڈاکٹر (Doctor):</b> ہر رات ایک کھلاڑی کو مرنے سے بچاتا ہے۔ خود کو بھی بچا سکتا ہے۔
<b>شکاری (Hunter):</b> اگر رات میں مارا جائے تو 75% امکان ہے کہ کسی بُرے کھلاڑی کو بھی ساتھ لے جائے۔
<b>نائٹ (Knight):</b> رات کا ایک حملہ برداشت کر لیتا ہے۔
<b>میئر (Mayor):</b> آپ کا ووٹ دو بار گنا جاتا ہے۔
<b>قاتل (Assassin):</b> پوری گیم میں ایک بار، رات میں، کسی کو بھی ختم کر سکتا ہے۔
<b>مردے زندہ کرنے والا (Necromancer):</b> پوری گیم میں ایک بار، اچھی ٹیم کے کسی مرے ہوئے کھلاڑی کو واپس زندہ کرتا ہے۔
<b>جوکر (Jester):</b> اچھی ٹیم میں ہے، لیکن مر جائے تو بھی جیت جاتا ہے۔
<b>گاؤں والا (Villager):</b> کوئی طاقت نہیں۔ بھیڑیوں کو پہچانیں اور ووٹ سے نکالیں۔`,
    hi:`सबको एक गुप्त किरदार का कार्ड मिलता है। ज़्यादातर खिलाड़ी <b>अच्छी</b> टीम में होते हैं, यानी गाँव। कुछ भेड़िए होते हैं जो <b>बुरी</b> टीम में हैं।
<b>रात:</b> भेड़िए किसी एक को ख़त्म करने के लिए चुनते हैं। कुछ अच्छे किरदार चुपके से अपनी ताक़त इस्तेमाल करते हैं।
<b>दिन:</b> सबको पता चलता है कि कौन ख़त्म हुआ, फिर बातचीत होती है और वोट से किसी को निकाला जाता है।
जब सारे बुरे खिलाड़ी ख़त्म हो जाएँ तो अच्छी टीम जीतती है। जब बुरे खिलाड़ी अच्छों के बराबर हो जाएँ तो बुरी टीम जीतती है।
गेम ख़ुद चलता है। बस अपनी स्क्रीन देखते रहें।
# किरदार
<b>भेड़िया (Werewolf):</b> हर रात बाक़ी भेड़ियों के साथ किसी को ख़त्म करने के लिए चुनता है। दिन में भोला बना रहता है।
<b>सरदार भेड़िया (Alpha Wolf):</b> भेड़ियों का लीडर। ज्योतिषी को अच्छा दिखता है।
<b>भेड़ियों का ओझा (Wolf Shaman):</b> पूरे गेम में एक बार, दिन में, किसी दूसरे बुरे खिलाड़ी को वोट से बचाता है।
<b>जलपरी (Siren):</b> बुरी टीम। अगर वोट से निकाली गई तो अगली रात अच्छों की सारी ताक़तें फ़ेल हो जाती हैं।
<b>ज्योतिषी (Seer):</b> हर रात जान लेता है कि एक खिलाड़ी अच्छा है या बुरा।
<b>डॉक्टर (Doctor):</b> हर रात एक खिलाड़ी को मरने से बचाता है। ख़ुद को भी बचा सकता है।
<b>शिकारी (Hunter):</b> अगर रात में मारा जाए तो 75% चांस है कि किसी बुरे खिलाड़ी को भी साथ ले जाए।
<b>योद्धा (Knight):</b> रात का एक हमला झेल लेता है।
<b>मेयर (Mayor):</b> आपका वोट दो बार गिना जाता है।
<b>हत्यारा (Assassin):</b> पूरे गेम में एक बार, रात में, किसी को भी ख़त्म कर सकता है।
<b>मुर्दे ज़िंदा करने वाला (Necromancer):</b> पूरे गेम में एक बार, अच्छी टीम के किसी मरे हुए खिलाड़ी को वापस ज़िंदा करता है।
<b>जोकर (Jester):</b> अच्छी टीम में है, लेकिन मर जाए तो भी जीत जाता है।
<b>गाँव वाला (Villager):</b> कोई ताक़त नहीं। भेड़ियों को पहचानें और वोट से निकालें।`,
  };

  /* ---------- Draw It ---------- */
  T.draw = {
    en:`The AI gives everyone the same thing to draw, like "Goku doing his taxes".
Draw it before the timer runs out. Play alone, or in teams on one shared canvas.
Tools: brush, eraser, fill bucket, colour picker, size, opacity, undo and redo.
Then every drawing gets a score out of 10, from the AI or from the other players.
The host reveals the drawings one by one. Most points after all the rounds wins.`,
    ar:`يعطي الذكاء الاصطناعي الجميع نفس الشيء ليرسموه، مثل "غوكو يدفع الضرائب".
ارسمه قبل أن ينتهي الوقت. العب وحدك، أو ضمن فريق على لوحة رسم مشتركة.
الأدوات: فرشاة، ممحاة، دلو تعبئة، منتقي ألوان، الحجم، الشفافية، تراجع وإعادة.
بعدها تحصل كل رسمة على درجة من 10، من الذكاء الاصطناعي أو من باقي اللاعبين.
يكشف المضيف الرسومات واحدة تلو الأخرى. صاحب أعلى النقاط بعد كل الجولات يفوز.`,
    ur:`AI سب کو ایک ہی چیز بنانے کو دیتا ہے، جیسے "گوکو اپنا ٹیکس بھر رہا ہے"۔
ٹائمر ختم ہونے سے پہلے اسے بنائیں۔ اکیلے کھیلیں، یا ٹیم میں ایک ہی کینوس پر مل کر۔
ٹولز: برش، ربڑ، رنگ بھرنے والی بالٹی، رنگ چننے والا، سائز، شفافیت، Undo اور Redo۔
پھر ہر ڈرائنگ کو 10 میں سے نمبر ملتے ہیں، AI سے یا باقی کھلاڑیوں سے۔
ہوسٹ ایک ایک کر کے ڈرائنگز دکھاتا ہے۔ سارے راؤنڈز کے بعد سب سے زیادہ پوائنٹس والا جیتتا ہے۔`,
    hi:`AI सबको एक ही चीज़ बनाने को देता है, जैसे "गोकू अपना टैक्स भर रहा है"।
टाइमर ख़त्म होने से पहले उसे बनाएँ। अकेले खेलें, या टीम में एक ही कैनवस पर मिलकर।
टूल्स: ब्रश, रबड़, रंग भरने वाली बाल्टी, रंग चुनने वाला, साइज़, पारदर्शिता, Undo और Redo।
फिर हर ड्रॉइंग को 10 में से नंबर मिलते हैं, AI से या बाक़ी खिलाड़ियों से।
होस्ट एक-एक करके ड्रॉइंग्स दिखाता है। सारे राउंड के बाद सबसे ज़्यादा पॉइंट्स वाला जीतता है।`,
  };

  /* ---------- Last Lantern (the card game) ---------- */
  T.lantern = {
    en:`Everyone gets a hand of cards. Empty your hand first to win the round.
On your turn, play a card that matches the top card's <b>colour</b> or its <b>number or symbol</b>.
Can't play? Draw a card. If it fits, you can play it straight away, or pass.
<b>Block</b> skips the next player. <b>Turn back</b> reverses the direction. <b>+2</b> makes the next player draw 2.
<b>Wild</b> lets you pick the colour. <b>Wild +4</b> also makes the next player draw 4.
Stacking (if the host turned it on): hit with a +2? Play your own +2 or a +4 to pass it on, bigger.
About to go down to one card? Tap <b>"Last card!"</b> first. If you forget, anyone can tap <b>"Catch!"</b> and you draw 2.
# Speed mode
Every turn is 10 seconds.
Holding the exact same card as the top one (same colour, same number)? Play it any time, even when it isn't your turn. Play carries on from you.`,
    ar:`كل لاعب يحصل على مجموعة أوراق. أول من يتخلّص من كل أوراقه يفوز بالجولة.
في دورك، العب ورقة تطابق الورقة العلوية في <b>اللون</b> أو في <b>الرقم أو الرمز</b>.
لا تستطيع اللعب؟ اسحب ورقة. إذا كانت مناسبة يمكنك لعبها فورًا، أو اضغط تمرير.
<b>Block</b> يتخطّى اللاعب التالي. <b>Turn back</b> يعكس الاتجاه. <b>+2</b> تجعل اللاعب التالي يسحب ورقتين.
<b>Wild</b> تتيح لك اختيار اللون. <b>Wild +4</b> تجعل اللاعب التالي يسحب 4 أيضًا.
التكديس (إذا فعّله المضيف): أصابتك +2؟ العب +2 أو +4 لتمرّرها للتالي بعدد أكبر.
ستبقى معك ورقة واحدة؟ اضغط <b>"Last card!"</b> أولًا. إذا نسيت، يمكن لأي لاعب الضغط على <b>"Catch!"</b> وتسحب ورقتين.
# وضع السرعة (Speed)
كل دور مدته 10 ثوانٍ.
معك نفس الورقة العلوية تمامًا (نفس اللون ونفس الرقم)؟ العبها في أي وقت، حتى لو لم يكن دورك. ويستمر اللعب من عندك.`,
    ur:`سب کو کچھ پتے ملتے ہیں۔ جو سب سے پہلے اپنے سارے پتے ختم کرے، وہ راؤنڈ جیتتا ہے۔
اپنی باری پر ایسا پتا کھیلیں جو اوپر والے پتے کے <b>رنگ</b> سے، یا اس کے <b>نمبر یا نشان</b> سے ملتا ہو۔
کھیل نہیں سکتے؟ ایک پتا اٹھائیں۔ اگر وہ مل جائے تو فوراً کھیل سکتے ہیں، یا Pass کریں۔
<b>Block</b> اگلے کھلاڑی کی باری چھین لیتا ہے۔ <b>Turn back</b> رخ الٹا کر دیتا ہے۔ <b>+2</b> سے اگلے کھلاڑی کو 2 پتے اٹھانے پڑتے ہیں۔
<b>Wild</b> سے آپ رنگ چن سکتے ہیں۔ <b>Wild +4</b> سے اگلے کھلاڑی کو 4 پتے بھی اٹھانے پڑتے ہیں۔
اسٹیکنگ (اگر ہوسٹ نے آن کی ہو): آپ پر +2 آیا؟ اپنا +2 یا +4 کھیل کر اسے بڑا کر کے آگے بھیج دیں۔
ایک پتا بچنے والا ہے؟ پہلے <b>"Last card!"</b> دبائیں۔ بھول گئے تو کوئی بھی <b>"Catch!"</b> دبا سکتا ہے اور آپ کو 2 پتے اٹھانے پڑیں گے۔
# اسپیڈ موڈ (Speed)
ہر باری صرف 10 سیکنڈ کی ہوتی ہے۔
آپ کے پاس بالکل وہی پتا ہے جو اوپر ہے (وہی رنگ، وہی نمبر)؟ اسے کبھی بھی کھیل دیں، چاہے آپ کی باری نہ ہو۔ کھیل آپ سے آگے چلے گا۔`,
    hi:`सबको कुछ पत्ते मिलते हैं। जो सबसे पहले अपने सारे पत्ते ख़त्म करे, वह राउंड जीतता है।
अपनी बारी पर ऐसा पत्ता खेलें जो ऊपर वाले पत्ते के <b>रंग</b> से, या उसके <b>नंबर या निशान</b> से मिलता हो।
खेल नहीं सकते? एक पत्ता उठाएँ। अगर वह मिल जाए तो तुरंत खेल सकते हैं, या Pass करें।
<b>Block</b> अगले खिलाड़ी की बारी छीन लेता है। <b>Turn back</b> दिशा उलट देता है। <b>+2</b> से अगले खिलाड़ी को 2 पत्ते उठाने पड़ते हैं।
<b>Wild</b> से आप रंग चुन सकते हैं। <b>Wild +4</b> से अगले खिलाड़ी को 4 पत्ते भी उठाने पड़ते हैं।
स्टैकिंग (अगर होस्ट ने चालू की हो): आप पर +2 आया? अपना +2 या +4 खेलकर उसे बड़ा करके आगे भेज दें।
एक पत्ता बचने वाला है? पहले <b>"Last card!"</b> दबाएँ। भूल गए तो कोई भी <b>"Catch!"</b> दबा सकता है और आपको 2 पत्ते उठाने पड़ेंगे।
# स्पीड मोड (Speed)
हर बारी सिर्फ़ 10 सेकंड की होती है।
आपके पास बिल्कुल वही पत्ता है जो ऊपर है (वही रंग, वही नंबर)? उसे कभी भी खेल दें, चाहे आपकी बारी न हो। खेल आपसे आगे चलेगा।`,
  };

  /* ---------- Forged Brush ---------- */
  T.forged = {
    en:`Everyone draws the same secret subject together on one shared canvas—except the <b>Forger</b>.
<b>Clueless Forger</b> mode: the Forger sees only the category and has to fake confident strokes. <b>Decoy Forger</b> mode: the Forger gets a similar subject and doesn't know they're the Forger.
Each artist gets their own ink colour. On your turn, draw <b>one continuous brushstroke</b>, then tap <b>"Lock stroke"</b> (or <b>"Redraw"</b> before time runs out).
Don't make your stroke too obvious—or the Forger will figure out the subject!
After all passes, inspect the finished painting: tap any artist's chip to spotlight only their strokes, or hit <b>"Replay"</b> to watch the drawing unfold stroke by stroke.
Vote on who you think the Forger is. If caught, the Forger gets one last guess at the real subject to steal the round!
# Points
Spot the Forger: +2. Forger escapes: +3, or +4 if an innocent artist was framed. Caught Forger guesses the subject: +3. Framing an innocent: -1.`,
    ar:`يرسم الجميع نفس الموضوع السرّي معًا على لوحة واحدة مشتركة—إلا <b>المزوّر (Forger)</b>.
وضع <b>Clueless Forger</b>: يرى المزوّر الفئة فقط وعليه التظاهر برسم خطوط واثقة. وضع <b>Decoy Forger</b>: يحصل المزوّر على موضوع قريب ولا يعرف أنه المزوّر.
يحصل كل رسام على لون حبر خاص به. في دورك، ارسم <b>ضربة فرشاة واحدة متصلة</b>، ثم اضغط <b>"Lock stroke"</b> (أو <b>"Redraw"</b> قبل انتهاء الوقت).
لا تجعل خطّك واضحًا جدًا—وإلا سيكتشف المزوّر الموضوع!
بعد انتهاء الجولات، افحص اللوحة: اضغط على اسم أي رسام لإبراز خطوطه فقط، أو اضغط <b>"Replay"</b> لمشاهدة الرسم خطوة بخطوة.
صوّت على من تظن أنه المزوّر. إذا انكشف، يحصل على محاولة أخيرة لتخمين الموضوع الحقيقي وسرقة الجولة!
# النقاط
كشف المزوّر: ‎+2. هروب المزوّر: ‎+3، أو ‎+4 إذا طُرد بريء. المزوّر المكشوف يخمّن الموضوع: ‎+3. التصويت ضد بريء: ‎-1.`,
    ur:`سب لوگ ایک ہی مشترکہ کینوس پر ایک خفیہ چیز مل کر بناتے ہیں—سوائے <b>جعلساز (Forger)</b> کے۔
<b>Clueless Forger</b> موڈ: جعلساز کو صرف کیٹیگری نظر آتی ہے اور اسے نقل کر کے لکیریں بنانی ہوتی ہیں۔ <b>Decoy Forger</b> موڈ: جعلساز کو ملتی جلتی چیز ملتی ہے اور اسے خود پتا نہیں ہوتا کہ وہ جعلساز ہے۔
ہر کھلاڑی کو اپنا الگ رنگ ملتا ہے۔ اپنی باری پر <b>ایک مسلسل لکیر</b> کھینچیں، پھر <b>"Lock stroke"</b> دبائیں (یا وقت ختم ہونے سے پہلے <b>"Redraw"</b> کریں)۔
اپنی لکیر بہت زیادہ آسان نہ بنائیں—ورنہ جعلساز فوراً سمجھ جائے گا!
ڈرائنگ مکمل ہونے کے بعد اس کا معائنہ کریں: کسی بھی کھلاڑی کے نام پر ٹیپ کر کے صرف اس کی لکیریں دیکھیں، یا <b>"Replay"</b> دبا کر پوری ڈرائنگ دوبارہ چلائیں۔
ووٹ دیں کہ جعلساز کون ہے۔ اگر پکڑا گیا تو اسے اصل چیز بوجھ کر راؤنڈ چرانے کا ایک آخری موقع ملتا ہے!
# پوائنٹس
جعلساز کو پکڑنا: ‎+2۔ جعلساز بچ جائے: ‎+3، اور اگر کوئی بےقصور پھنس جائے تو ‎+4۔ پکڑا گیا جعلساز چیز بوجھ لے: ‎+3۔ بےقصور کو ووٹ دینا: ‎-1۔`,
    hi:`सब लोग एक ही साझा कैनवस पर एक गुप्त चीज़ मिलकर बनाते हैं—सिवाय <b>नक़लची (Forger)</b> के।
<b>Clueless Forger</b> मोड: नक़लची को सिर्फ़ कैटेगरी दिखती है और उसे अंदाज़े से लाइन बनानी होती है। <b>Decoy Forger</b> मोड: नक़लची को मिलती-जुलती चीज़ मिलती है और उसे पता नहीं होता कि वह नक़लची है।
हर कलाकार को अपना अलग रंग मिलता है। अपनी बारी पर <b>एक लगातार ब्रशस्ट्रोक</b> बनाएँ, फिर <b>"Lock stroke"</b> दबाएँ (या समय ख़त्म होने से पहले <b>"Redraw"</b> करें)।
अपनी लाइन बहुत आसान न बनाएँ—वरना नक़लची असली चीज़ समझ जाएगा!
पेंटिंग पूरी होने के बाद जाँच करें: किसी भी कलाकार के नाम पर टैप करके सिर्फ़ उसकी लाइनें देखें, या <b>"Replay"</b> दबाकर पूरी पेंटिंग एक-एक लाइन बनते देखें।
वोट करें कि नक़लची कौन है। पकड़े जाने पर उसे असली चीज़ बूझकर राउंड चुराने का एक आख़िरी मौक़ा मिलता है!
# पॉइंट्स
नक़लची को पकड़ना: +2। नक़लची बच जाए: +3, और अगर कोई बेक़सूर फँस जाए तो +4। पकड़ा गया नक़लची चीज़ बूझ ले: +3। बेक़सूर को वोट देना: -1।`,
  };

  /* ---------- Broken Scroll ---------- */
  T.scroll = {
    en:`Every player starts their own scroll by writing a funny prompt (or tap <b>"Inspire me"</b> for a random idea).
Then the scrolls pass around the table! On each step you either <b>draw</b> what the last person wrote, or <b>guess</b> what the last person drew.
Tools: brush, eraser, fill bucket, colour swatches, brush sizes, undo and redo. Tap <b>"I'm done!"</b> when finished (your work also auto-saves when the timer ends).
When all steps finish, everyone watches each scroll unroll panel by panel in the <b>Reveal Theater</b>, reacting live with emojis—and you can save any scroll as a <b>Comic Strip PNG</b>!
# Modes
<b>Classic Telephone:</b> alternates between writing and drawing until the prompt mutates completely.
<b>Speed Chaos:</b> frantic 45s drawing and 20s guessing timers.
<b>Memory Knock-Off:</b> study the previous drawing for only 7 seconds, then redraw it from memory!`,
    ar:`يبدأ كل لاعب لفّافته بكتابة فكرة مضحكة (أو اضغط <b>"Inspire me"</b> لفكرة عشوائية).
ثم تمرّ اللفافات حول الطاولة! في كل خطوة إمّا أن <b>ترسم</b> ما كتبه اللاعب السابق، أو <b>تخمّن</b> ما رسمه.
الأدوات: فرشاة، ممحاة، دلو تعبئة، ألوان، أحجام، تراجع وإعادة. اضغط <b>"I'm done!"</b> عند الانتهاء (ويُحفظ عملك تلقائيًا عند انتهاء الوقت).
عند انتهاء كل الخطوات، يشاهد الجميع كل لفّافة تُفتح خطوة بخطوة في <b>مسرح الكشف</b> مع تفاعلات مباشرة—ويمكنك حفظ أي لفّافة كصورة شريط قصصي <b>Comic Strip PNG</b>!
# الأوضاع
<b>Classic Telephone:</b> يتناوب بين الكتابة والرسم حتى تتحوّل الفكرة تمامًا.
<b>Speed Chaos:</b> مؤقّتات سريعة ومجنونة (45 ثانية للرسم و20 ثانية للتخمين).
<b>Memory Knock-Off:</b> شاهد الرسمة السابقة لـ 7 ثوانٍ فقط، ثم أعد رسمها من الذاكرة!`,
    ur:`ہر کھلاڑی ایک مزاحیہ خیال لکھ کر اپنا اسکرول شروع کرتا ہے (یا رینڈم آئیڈیا کے لیے <b>"Inspire me"</b> دبائیں)۔
پھر اسکرولز سب کے درمیان گھومتے ہیں! ہر مرحلے میں آپ یا تو پچھلے کھلاڑی کی لکھی ہوئی چیز <b>بناتے</b> ہیں، یا اس کی بنائی ہوئی ڈرائنگ کا <b>اندازہ</b> لگاتے ہیں۔
ٹولز: برش، ربڑ، رنگ بھرنے والی بالٹی، رنگ، سائز، Undo اور Redo۔ مکمل ہونے پر <b>"I'm done!"</b> دبائیں (وقت ختم ہونے پر آپ کا کام خود بخود محفوظ ہو جاتا ہے)۔
سارے مراحل کے بعد سب مل کر <b>Reveal Theater</b> میں ہر اسکرول کو ایک ایک کر کے کھلتے دیکھتے ہیں، ایموجیز سے ردعمل دیتے ہیں—اور کسی بھی اسکرول کو <b>Comic Strip PNG</b> کے طور پر محفوظ کر سکتے ہیں!
# موڈز
<b>Classic Telephone:</b> باری باری لکھنا اور بنانا، جب تک اصل خیال بالکل بدل نہ جائے۔
<b>Speed Chaos:</b> تیز ترین ٹائمر (45 سیکنڈ ڈرائنگ اور 20 سیکنڈ اندازہ)۔
<b>Memory Knock-Off:</b> پچھلی ڈرائنگ کو صرف 7 سیکنڈ دیکھیں، پھر یادداشت سے دوبارہ بنائیں!`,
    hi:`हर खिलाड़ी एक मज़ेदार आइडिया लिखकर अपना स्क्रॉल शुरू करता है (या रैंडम आइडिया के लिए <b>"Inspire me"</b> दबाएँ)।
फिर स्क्रॉल सबके बीच घूमते हैं! हर स्टेप में आप या तो पिछले खिलाड़ी की लिखी बात <b>ड्रॉ</b> करते हैं, या उसकी ड्रॉइंग का <b>अंदाज़ा</b> लगाते हैं।
टूल्स: ब्रश, रबड़, फ़िल बकेट, रंग, साइज़, Undo और Redo। पूरा होने पर <b>"I'm done!"</b> दबाएँ (टाइमर ख़त्म होने पर आपका काम अपने-आप सेव हो जाता है)।
सारे स्टेप पूरे होने पर सब मिलकर <b>Reveal Theater</b> में हर स्क्रॉल को एक-एक करके खुलते देखते हैं, इमोजी से रिएक्ट करते हैं—और किसी भी स्क्रॉल को <b>Comic Strip PNG</b> के रूप में सेव कर सकते हैं!
# मोड्स
<b>Classic Telephone:</b> बारी-बारी से लिखना और बनाना, जब तक असली आइडिया पूरी तरह बदल न जाए।
<b>Speed Chaos:</b> तेज़-तर्रार टाइमर (45 सेकंड ड्रॉइंग और 20 सेकंड अंदाज़ा)।
<b>Memory Knock-Off:</b> पिछली ड्रॉइंग को सिर्फ़ 7 सेकंड देखें, फिर याददाश्त से दोबारा बनाएँ!`,
  };

  /* ---------- Guess the Silhouette ---------- */
  T.silhouette = {
    en:`Race your friends to identify characters and answer speed trivia!
<b>Character Reveal:</b> an anime character portrait starts heavily disguised as a black silhouette, heavy blur, or extreme zoom and clears up over 15 seconds. Answer faster for up to <b>+1000</b> points!
Tap one of the 4 choices—or in <b>Type Answer</b> mode, type the character's name before anyone else.
<b>Higher or Lower:</b> two famous anime characters face off. Pick which one has more AniList favourites!
<b>AI Speed Trivia:</b> fast 4-choice questions on anime, movies, food, or any custom topic the host enters.
# Streaks & Bonus
Chain correct answers in a row to build a <b>Streak Bonus</b> (up to +300 extra points per round!).`,
    ar:`سابق أصدقاءك في التعرّف على الشخصيات وأسئلة السرعة!
<b>Character Reveal:</b> تبدأ صورة شخصية الأنمي مخفيّة كظل أسود أو ضبابية أو مقرّبة جدًا وتوضح تدريجيًا خلال 15 ثانية. أجب أسرع لتحصل حتى <b>+1000</b> نقطة!
اضغط أحد الخيارات الأربعة—أو في وضع <b>Type Answer</b> اكتب اسم الشخصية قبل الجميع.
<b>Higher or Lower:</b> شخصيتا أنمي شهيرتان وجهًا لوجه. اختر أيهما لديه عدد أكبر من المفضّلين على AniList!
<b>AI Speed Trivia:</b> أسئلة سريعة من 4 خيارات عن الأنمي أو الأفلام أو الطعام أو أي موضوع يكتبه المضيف.
# السلسلة والمكافآت
أجب بشكل صحيح متتالٍ لبناء <b>Streak Bonus</b> (حتى +300 نقطة إضافية في كل جولة!).`,
    ur:`اپنے دوستوں سے مقابلہ کریں اور تیزی سے کردار پہچانیں!
<b>Character Reveal:</b> ایک اینیمے کردار کی تصویر کالے سائے، دھندلے پن، یا زوم میں چھپی ہوتی ہے اور 15 سیکنڈ میں صاف ہوتی جاتی ہے۔ جتنی جلدی جواب دیں گے، اتنے زیادہ پوائنٹس (<b>+1000</b> تک)!
4 آپشنز میں سے ایک چنیں—یا <b>Type Answer</b> موڈ میں کردار کا نام سب سے پہلے ٹائپ کریں۔
<b>Higher or Lower:</b> دو مشہور اینیمے کردار آمنے سامنے۔ چنیں کہ AniList پر کس کے زیادہ فینز ہیں!
<b>AI Speed Trivia:</b> اینیمے، فلموں، کھانے، یا ہوسٹ کے کسی بھی موضوع پر تیز ترین 4-آپشن سوالات۔
# مسلسل درست جوابات
لگاتار صحیح جوابات دے کر <b>Streak Bonus</b> بنائیں (ہر راؤنڈ میں +300 اضافی پوائنٹس تک!)۔`,
    hi:`अपने दोस्तों के साथ रेस लगाएँ और तेज़ी से किरदार पहचानें!
<b>Character Reveal:</b> एक एनीमे किरदार की तस्वीर काले साये, धुंधलेपन, या ज़ूम में छुपी होती है और 15 सेकंड में साफ़ होती जाती है। जितनी जल्दी जवाब देंगे, उतने ज़्यादा पॉइंट्स (<b>+1000</b> तक)!
4 विकल्पों में से एक चुनें—या <b>Type Answer</b> मोड में किरदार का नाम सबसे पहले टाइप करें।
<b>Higher or Lower:</b> दो मशहूर एनीमे किरदार आमने-सामने। चुनें कि AniList पर किसके ज़्यादा फ़ैन्स हैं!
<b>AI Speed Trivia:</b> एनीमे, फ़िल्मों, खाने, या होस्ट के किसी भी विषय पर तेज़ 4-ऑप्शन सवाल।
# स्ट्रीक बोनस
लगातार सही जवाब देकर <b>Streak Bonus</b> बनाएँ (हर राउंड में +300 एक्स्ट्रा पॉइंट्स तक!)।`,
  };

  /* ---------- Festival Dial ---------- */
  T.dial = {
    en:`Every turn, one player becomes the <b>Psychic</b> and sees a hidden target spot on a two-sided spectrum (like <b>Overrated ↔ Underrated</b> or <b>Harmless ↔ Pure Menace</b>).
The Psychic writes <b>one short clue</b> that sits at that exact spot on the spectrum, then taps <b>"Send clue"</b>.
Everyone else drags the needle on the festival fan dial (or slides the bar) to where they think the target is hiding, then taps <b>"Lock in"</b>.
When the screen opens, the target wedges appear and everyone argues about the Psychic's clue!
# Points
<b>Bullseye</b> (within 4): +4 pts. <b>Close</b> (within 10): +3 pts. <b>Warm</b> (within 18): +2 pts.
The Psychic also scores points based on the best guess (up to +3 pts), so good clues pay off!`,
    ar:`في كل دور يصبح أحد اللاعبين <b>العرّاف (Psychic)</b> ويرى هدفًا مخفيًا على مقياس من طرفين (مثل <b>Overrated ↔ Underrated</b> أو <b>Harmless ↔ Pure Menace</b>).
يكتب العرّاف <b>تلميحًا واحدًا قصيرًا</b> يناسب ذلك الموضع تمامًا، ثم يضغط <b>"Send clue"</b>.
يحرّك باقي اللاعبين إبرة المروحة (أو الشريط) إلى المكان الذي يظنون أن الهدف يختبئ فيه، ثم يضغطون <b>"Lock in"</b>.
عند الكشف تظهر مناطق الهدف وتبدأ النقاشات المضحكة حول التلميح!
# النقاط
<b>إصابة مباشرة (Bullseye)</b>: ‎+4 نقاط. <b>قريب (Close)</b>: ‎+3 نقاط. <b>دافئ (Warm)</b>: ‎+2 نقطة.
يكسب العرّاف أيضًا نقاطًا بناءً على أفضل تخمين (حتى +3 نقاط)، لذا التلميحات الذكية مربحة!`,
    ur:`ہر باری پر ایک کھلاڑی <b>Psychic</b> بنتا ہے اور اسے دو سروں والے پیمانے پر ایک خفیہ نشان نظر آتا ہے (جیسے <b>Overrated ↔ Underrated</b> یا <b>Harmless ↔ Pure Menace</b>)۔
Psychic اس جگہ کے مطابق <b>ایک چھوٹا سا اشارہ</b> لکھتا ہے اور <b>"Send clue"</b> دباتا ہے۔
باقی سب کھلاڑی پنکھے کی سوئی کو گھما کر اس جگہ رکھتے ہیں جہاں ان کے خیال میں خفیہ نشان ہے، اور <b>"Lock in"</b> دباتے ہیں۔
جب پردہ کھلتا ہے تو خفیہ نشان سامنے آتا ہے اور اشارے پر مزیدار بحث شروع ہو جاتی ہے!
# پوائنٹس
<b>Bullseye</b> (بالکل نشانے پر): ‎+4 پوائنٹس۔ <b>Close</b> (قریب): ‎+3 پوائنٹس۔ <b>Warm</b> (تھوڑا قریب): ‎+2 پوائنٹس۔
Psychic کو بھی بہترین اندازے کے مطابق پوائنٹس ملتے ہیں (‎+3 تک)، اس لیے اچھا اشارہ دینا فائدہ مند ہے!`,
    hi:`हर बारी पर एक खिलाड़ी <b>Psychic</b> बनता है और उसे दो सिरों वाले स्केल पर एक छुपा हुआ टारगेट दिखता है (जैसे <b>Overrated ↔ Underrated</b> या <b>Harmless ↔ Pure Menace</b>)।
Psychic उस जगह के हिसाब से <b>एक छोटा सा क्लू</b> लिखता है और <b>"Send clue"</b> दबाता है।
बाक़ी सब खिलाड़ी पंखे की सुई घुमाकर वहाँ रखते हैं जहाँ उन्हें टारगेट लगता है, और <b>"Lock in"</b> दबाते हैं।
पर्दा खुलने पर टारगेट सामने आता है और क्लू पर मज़ेदार बहस छिड़ जाती है!
# पॉइंट्स
<b>Bullseye</b> (बिल्कुल निशाने पर): +4 पॉइंट्स। <b>Close</b> (क़रीब): +3 पॉइंट्स। <b>Warm</b> (थोड़ा क़रीब): +2 पॉइंट्स।
Psychic को भी सबसे अच्छे अंदाज़े के हिसाब से पॉइंट्स मिलते हैं (+3 तक), इसलिए अच्छा क्लू देना फ़ायदेमंद है!`,
  };

  /* ---------- Caption Clash ---------- */
  T.clash = {
    en:`Each round you get <b>2 funny prompts</b> (anime, party, or custom theme)—and one secret opponent is answering the exact same prompt!
Write the funniest, most unhinged reply you can think of before time runs out, then tap <b>"Lock answers"</b>.
Next, every matchup goes <b>head-to-head</b> on the big stage. Everyone who wasn't in that matchup votes for the funnier answer!
After the votes tally, the <b>AI Judge</b> drops a savage one-liner roasting the losing answer.
# Points
Each vote is worth <b>+100 pts</b>. Win every single vote in a matchup for a <b>CLASH SWEEP (+250 bonus!)</b>.
The final round is worth <b>2× Double Points</b>—anybody can steal the crown at the end!`,
    ar:`في كل جولة تحصل على <b>سؤالين مضحكين</b>—وهناك منافس سرّي يكتب إجابة لنفس السؤال!
اكتب أطرف وأجنّ إجابة تخطر ببالك قبل انتهاء الوقت، ثم اضغط <b>"Lock answers"</b>.
بعدها تُعرض كل مواجهة <b>وجهًا لوجه</b> على المسرح. يصوّت بقية اللاعبين للإجابة الأطرف!
بعد إعلان الأصوات، يعلّق <b>الذكاء الاصطناعي</b> بسخرية لاذعة على الإجابة الخاسرة.
# النقاط
كل صوت يمنح <b>+100 نقطة</b>. اكتسح كل الأصوات لتحصل على <b>CLASH SWEEP (+250 مكافأة!)</b>.
الجولة الأخيرة تمنح <b>ضعف النقاط (2×)</b>—يمكن لأي لاعب خطف الفوز في النهاية!`,
    ur:`ہر راؤنڈ میں آپ کو <b>2 مزاحیہ سوال</b> ملتے ہیں—اور ایک خفیہ حریف بالکل اسی سوال کا جواب لکھ رہا ہوتا ہے!
وقت ختم ہونے سے پہلے سب سے مزاحیہ جواب لکھیں اور <b>"Lock answers"</b> دبائیں۔
پھر ہر مقابلہ اسٹیج پر <b>آمنے سامنے</b> آتا ہے۔ باقی تمام کھلاڑی زیادہ مزاحیہ جواب کو ووٹ دیتے ہیں!
ووٹ گنے جانے کے بعد <b>AI Judge</b> ہارنے والے جواب کا زبردست مذاق اڑاتا ہے۔
# پوائنٹس
ہر ووٹ کے <b>+100 پوائنٹس</b>۔ سارے ووٹ جیتنے پر <b>CLASH SWEEP (+250 بونس!)</b>۔
آخری راؤنڈ میں <b>2× ڈبل پوائنٹس</b> ملتے ہیں—کوئی بھی آخر میں بازی پلٹ سکتا ہے!`,
    hi:`हर राउंड में आपको <b>2 मज़ेदार प्रॉम्प्ट</b> मिलते हैं—और एक गुप्त प्रतिद्वंद्वी भी उसी प्रॉम्प्ट का जवाब लिख रहा होता है!
समय ख़त्म होने से पहले सबसे मज़ेदार जवाब लिखें और <b>"Lock answers"</b> दबाएँ।
फिर हर मुक़ाबला स्टेज पर <b>आमने-सामने</b> आता है। बाक़ी सभी खिलाड़ी ज़्यादा मज़ेदार जवाब को वोट देते हैं!
वोट गिने जाने के बाद <b>AI Judge</b> हारने वाले जवाब की ज़बरदस्त रोस्टिंग करता है।
# पॉइंट्स
हर वोट के <b>+100 पॉइंट्स</b>। सारे वोट जीतने पर <b>CLASH SWEEP (+250 बोनस!)</b>।
आख़िरी राउंड में <b>2× डबल पॉइंट्स</b> मिलते हैं—कोई भी अंत में बाज़ी पलट सकता है!`,
  };

  /* ---------- Fox's Bluff ---------- */
  T.bluff = {
    en:`Every player starts with 4 festival coasters: <b>3 Sakura Blossoms</b> (safe) and <b>1 Cursed Fox Mask</b> (trap).
<b>1. Secret Place:</b> everyone puts 1 coaster face-down in front of them.
<b>2. Stack or Bid:</b> on your turn, either stack another coaster face-down onto your pile, OR start the bidding ("I can flip X safe blossoms!").
<b>3. Bidding War:</b> once bidding starts, everyone must either <b>Raise</b> the number or <b>Pass</b> until one Challenger remains.
<b>4. The Flip:</b> the Challenger must flip <b>all of their own coasters first</b>, then tap other players' piles one by one.
Flip enough Sakura Blossoms and you score <b>+1 point</b> (first to the goal wins!).
Hit a <b>Cursed Fox Mask</b>? BOOM—you lose one coaster permanently for the rest of the match. Lose all 4 coasters and you're eliminated!`,
    ar:`يبدأ كل لاعب بـ 4 أقراص مهرجان: <b>3 أزهار ساكورا</b> (آمنة) و<b>1 قناع ثعلب ملعون</b> (فخ).
<b>1. الوضع السرّي:</b> يضع كل لاعب قرصًا واحدًا مقلوبًا أمامه.
<b>2. تكديس أو مزايدة:</b> في دورك إمّا أن تضيف قرصًا آخر مقلوبًا فوق كومتك، أو تبدأ المزايدة ("أستطيع قلب X أزهار آمنة!").
<b>3. حرب المزايدة:</b> بمجرد بدء المزايدة، يجب إمّا <b>رفع الرقم (Raise)</b> أو <b>التمرير (Pass)</b> حتى يبقى متحدٍّ واحد.
<b>4. القلب:</b> يجب على المتحدّي قلب <b>كل أقراصه أولًا</b>، ثم اختيار أقراص الآخرين واحدًا تلو الآخر.
اقلب العدد المطلوب من أزهار الساكورا لتكسب <b>+1 نقطة</b> (أول من يصل للهدف يفوز!).
كشفت <b>قناع الثعلب</b>؟ بوم—تخسر قرصًا واحدًا للأبد حتى نهاية المباراة. وإذا فقدت كل أقراصك تخرج من اللعب!`,
    ur:`ہر کھلاڑی کے پاس 4 تہواری کوسٹرز ہوتے ہیں: <b>3 ساکورا پھول</b> (محفوظ) اور <b>1 منحوس لومڑی کا ماسک</b> (جال)۔
<b>1. خفیہ چال:</b> سب ایک کوسٹر الٹا کر کے اپنے سامنے رکھتے ہیں۔
<b>2. ڈھیر یا بولی:</b> اپنی باری پر یا تو اپنے ڈھیر پر ایک اور کوسٹر الٹا رکھیں، یا بولی شروع کریں ("میں X محفوظ پھول پلٹ سکتا ہوں!")۔
<b>3. بولی کا مقابلہ:</b> بولی شروع ہونے پر سب کو یا تو <b>Raise</b> کرنا ہوتا ہے یا <b>Pass</b>، جب تک صرف ایک چیلنجر باقی نہ رہ جائے۔
<b>4. پلٹنے کی باری:</b> چیلنجر کو پہلے <b>اپنے سارے کوسٹرز پلٹنے ہوتے ہیں</b>، پھر دوسروں کے ڈھیر پر ٹیپ کر کے پلٹنے ہوتے ہیں۔
مطلوبہ محفوظ پھول پلٹ لیے تو <b>+1 پوائنٹ</b> (ہدف پورا کرنے والا جیتتا ہے!)۔
<b>لومڑی کا ماسک</b> نکل آیا؟ دھماکہ—آپ کا ایک کوسٹر پورے میچ کے لیے ضائع ہو جاتا ہے۔ چاروں ختم ہونے پر آپ باہر!`,
    hi:`हर खिलाड़ी के पास 4 कोस्टर होते हैं: <b>3 साकुरा फूल</b> (सुरक्षित) और <b>1 शापित लोमड़ी मास्क</b> (जाल)।
<b>1. गुप्त चाल:</b> सब एक कोस्टर उल्टा करके अपने सामने रखते हैं।
<b>2. स्टैक या बोली:</b> अपनी बारी पर या तो अपने ढेर पर एक और कोस्टर उल्टा रखें, या बोली शुरू करें ("मैं X सुरक्षित फूल पलट सकता हूँ!")।
<b>3. बोली की जंग:</b> बोली शुरू होने पर सबको या तो <b>Raise</b> करना होता है या <b>Pass</b>, जब तक सिर्फ़ एक चैलेंजर न बचे।
<b>4. पलटने की बारी:</b> चैलेंजर को पहले <b>अपने सारे कोस्टर पलटने होते हैं</b>, फिर दूसरों के ढेर पर टैप करके पलटने होते हैं।
उतने सुरक्षित फूल पलट लिए तो <b>+1 पॉइंट</b> (लक्ष्य पूरा करने वाला जीतता है!)।
<b>लोमड़ी का मास्क</b> निकल आया? धमाका—आपका एक कोस्टर पूरे मैच के लिए चला जाता है। चारों ख़त्म होने पर आप बाहर!`,
  };

  /* ---------- Forehead Mask ---------- */
  T.mask = {
    en:`Play <b>Which Character Am I?</b>, <b>Which Anime Am I?</b> (with anime genre filters!), Movies & Games, Animals & Objects, Custom AI topics, or <b>Friends Pick</b>!
Everyone sees the portrait or anime poster stuck to your forehead—except YOU. Your own card stays masked with the round's theme badge so you always know what world you're guessing in.
Stuck? Tap <b>"Unlock Hint"</b> on your mystery card for progressive clues (Genre & Era → Starting letter & word count → Big Clue), or let friends send you a subtle 1-word nudge!
On your turn, tap a starter question, type your own, or ask out loud on Discord voice chat and hit <b>"Asked on VC"</b>. Everyone taps <b>Yes</b>, <b>No</b>, or <b>Kinda</b> and answers save into your personal <b>Clue Log</b>.
Think you know who you are? Type your answer and hit <b>"Guess!"</b>—earlier finishers earn more points!`,
    ar:`يحصل كل لاعب على شخصية أو شيء سرّي مُلصق على جبينه. ترى بطاقات <b>الجميع</b>، بينما تبقى بطاقتك مخفيّة خلف قناع المهرجان!
في وضع <b>Friends Pick</b>، يختار كل لاعب سرًّا الشخصية التي ستوضع على جبين اللاعب التالي قبل بدء الجولة.
في دورك، اسأل سؤال <b>نعم أو لا</b>—إمّا بكتابته أو طرحه صوتيًا على Discord والضغط على <b>"Asked on VC"</b>!
يرد البقية بـ <b>Yes</b> أو <b>No</b> أو <b>Kinda</b>، وتُحفظ كل الإجابات تلقائيًا في <b>سجل التلميحات (Clue Log)</b> الخاص بك.
تظن أنك عرفت من أنت؟ اكتب اسمك في خانة التخمين واضغط <b>"Guess!"</b>—من يكتشف هويته أسرع يكسب نقاطًا أكثر!`,
    ur:`ہر کھلاڑی کے ماتھے پر ایک خفیہ کردار یا چیز چپکی ہوتی ہے۔ آپ <b>باقی سب</b> کے کارڈ دیکھ سکتے ہیں، لیکن آپ کا اپنا کارڈ ماسک کے پیچھے چھپا ہوتا ہے!
<b>Friends Pick</b> موڈ میں راؤنڈ شروع ہونے سے پہلے ہر کھلاڑی چپکے سے اگلے کھلاڑی کا کردار خود چنتا ہے۔
اپنی باری پر <b>ہاں / نہیں والا سوال</b> پوچھیں—باکس میں لکھیں یا ڈسکارڈ وائس پر بول کر <b>"Asked on VC"</b> دبائیں!
باقی سب <b>Yes</b>، <b>No</b> یا <b>Kinda</b> پر ٹیپ کرتے ہیں۔ سارے جوابات آپ کے ذاتی <b>Clue Log</b> میں محفوظ ہوتے رہتے ہیں۔
لگتا ہے آپ سمجھ گئے کہ آپ کون ہیں؟ گیس باکس میں نام لکھیں اور <b>"Guess!"</b> دبائیں—پہلے بوجھنے والوں کو زیادہ پوائنٹس ملتے ہیں!`,
    hi:`हर खिलाड़ी के माथे पर एक गुप्त किरदार या चीज़ चिपकी होती है। आप <b>बाक़ी सबके</b> कार्ड देख सकते हैं, लेकिन आपका अपना कार्ड मास्क के पीछे छुपा रहता है!
<b>Friends Pick</b> मोड में राउंड शुरू होने से पहले हर खिलाड़ी चुपके से अगले खिलाड़ी का किरदार ख़ुद चुनता है।
अपनी बारी पर <b>हाँ / नहीं वाला सवाल</b> पूछें—बॉक्स में लिखें या डिस्कॉर्ड वॉइस पर बोलकर <b>"Asked on VC"</b> दबाएँ!
बाक़ी सब <b>Yes</b>, <b>No</b> या <b>Kinda</b> पर टैप करते हैं। सारे जवाब आपके पर्सनल <b>Clue Log</b> में सेव होते रहते हैं।
लगता है आप समझ गए कि आप कौन हैं? गेस बॉक्स में नाम लिखें और <b>"Guess!"</b> दबाएँ—पहले पहचानने वालों को ज़्यादा पॉइंट्स मिलते हैं!`,
  };

  /* ---------- Guess the OP & Songs ---------- */
  T.op = {
    en:`Turn up your volume and race friends to name the track from live 30-second previews!
Pick <b>Anime OPs &amp; EDs</b> (All, Shounen Bangers, Modern 2019+, Classics, or Movies &amp; Romance)—or switch to normal songs: <b>Global Pop</b>, <b>Hip-Hop &amp; Rap</b>, <b>K-Pop</b>, <b>Rock</b>, <b>Bollywood &amp; Desi</b>, <b>All Songs Mix</b>, or type any <b>Custom Artist / Topic</b>!
In <b>4 Choices</b> mode, tap the matching option (or press keys <b>1–4</b>) as fast as you can.
In <b>Type Name</b> mode, type the anime title, song name, or artist—small typos are forgiven!
# Scoring &amp; Streaks
Faster correct answers earn up to <b>+1000</b> points. Chain correct tracks in a row for a <b>Streak Bonus</b> (+150 extra per streak level)!`,
    ar:`ارفع الصوت وسابق أصدقاءك لمعرفة الأغنية من مقاطع حقيقية مدتها 30 ثانية!
اختر <b>Anime OPs &amp; EDs</b> (الكل، شونين، حديث، كلاسيكي، أو أفلام ورومانسية)—أو اختر أغاني عادية: <b>Global Pop</b> أو <b>Hip-Hop &amp; Rap</b> أو <b>K-Pop</b> أو <b>Rock</b> أو <b>Bollywood &amp; Desi</b> أو ابحث عن أي <b>فنان مخصص</b>!
في وضع <b>4 Choices</b>، اضغط على الخيار الصحيح (أو مفاتيح <b>1–4</b>) بأسرع ما يمكن.
في وضع <b>Type Name</b>، اكتب اسم الأنمي أو الأغنية أو الفنان—والأخطاء الإملائية البسيطة مقبولة!
# النقاط والسلسلة
الإجابات الأسرع تمنح حتى <b>+1000</b> نقطة، ومع كل إجابة صحيحة متتالية تحصل على مكافأة سلسلة إضافية!`,
    ur:`آواز تیز کریں اور 30 سیکنڈ کے لائیو میوزک کلپ سے گانا پہچاننے میں دوستوں سے مقابلہ کریں!
<b>Anime OPs &amp; EDs</b> منتخب کریں (آل، شونن، ماڈرن، کلاسک، یا موویز)—یا عام گانے کھیلیں: <b>Global Pop</b>، <b>Hip-Hop &amp; Rap</b>، <b>K-Pop</b>، <b>Rock</b>، <b>Bollywood &amp; Desi</b>، یا کوئی بھی <b>Custom Artist</b> سرچ کریں!
<b>4 Choices</b> موڈ میں صحیح آپشن پر ٹیپ کریں (یا کی بورڈ پر <b>1–4</b> دبائیں)۔
<b>Type Name</b> موڈ میں اینیمے، گانے، یا گلوکار کا نام ٹائپ کریں—چھوٹی اسپیلنگ کی غلطیاں معاف ہیں!
# پوائنٹس اور اسٹریک
جتنی جلدی صحیح جواب دیں گے اتنے زیادہ پوائنٹس (<b>+1000</b> تک)، اور لگاتار صحیح جوابات پر اضافی <b>Streak Bonus</b> ملتا ہے!`,
    hi:`आवाज़ बढ़ाएँ और 30 सेकंड के लाइव म्यूज़िक क्लिप से गाना पहचानने में दोस्तों से रेस लगाएँ!
<b>Anime OPs &amp; EDs</b> चुनें (ऑल, शोनन, मॉडर्न, क्लासिक, या मूवीज़)—या नॉर्मल गाने खेलें: <b>Global Pop</b>, <b>Hip-Hop &amp; Rap</b>, <b>K-Pop</b>, <b>Rock</b>, <b>Bollywood &amp; Desi</b>, या कोई भी <b>Custom Artist</b> सर्च करें!
<b>4 Choices</b> मोड में सही विकल्प चुनें (या कीबोर्ड पर <b>1–4</b> दबाएँ)।
<b>Type Name</b> मोड में एनीमे, गाने, या सिंगर का नाम टाइप करें—छोटी स्पेलिंग की ग़लतियाँ माफ़ हैं!
# स्कोर और स्ट्रीक
जितनी जल्दी सही जवाब देंगे उतने ज़्यादा पॉइंट्स (<b>+1000</b> तक), और लगातार सही जवाबों पर एक्स्ट्रा <b>Streak Bonus</b> मिलता है!`,
  };

  /* ---------- the sheet ---------- */
  const css = `
.howto-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;margin-top:14px;border:1px solid var(--line-2,rgba(255,255,255,.2));background:rgba(255,255,255,.05);color:inherit;border-radius:14px;padding:13px 16px;font:700 15px var(--body,system-ui);cursor:pointer;transition:background .15s,border-color .15s}
.howto-btn:hover{background:rgba(255,255,255,.1);border-color:color-mix(in srgb,var(--lantern,#FF3E78) 55%,var(--line-2))}
.howto-btn svg{width:18px;height:18px}
.howto-btn small{font-weight:600;opacity:.65;font-size:12px}
.howto-scrim{position:fixed;inset:0;z-index:90;background:rgba(4,6,14,.74);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);display:flex;align-items:flex-end;justify-content:center;animation:howtoFade .2s}
@media (min-width:700px){.howto-scrim{align-items:center;padding:24px}}
.howto{background:var(--night-2,#12172B);color:var(--fg,#F4F6FF);border:1px solid var(--line-2,rgba(255,255,255,.18));width:min(640px,100%);max-height:88vh;max-height:88svh;border-radius:22px 22px 0 0;display:grid;grid-template-rows:auto auto 1fr auto;overflow:hidden;box-shadow:0 -20px 60px rgba(0,0,0,.78);animation:howtoUp .32s cubic-bezier(.2,.9,.3,1)}
@media (min-width:700px){.howto{border-radius:22px}}
.howto header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 18px 10px}
.howto header h2{font-size:24px;margin:0}
.howto .x{border:1px solid var(--line,rgba(255,255,255,.12));background:rgba(255,255,255,.07);color:inherit;width:36px;height:36px;border-radius:50%;font-size:20px;line-height:1;cursor:pointer;flex:none}
.howto .langs{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:4px 18px 12px}
.howto .langs button{border:1.5px solid var(--line,rgba(255,255,255,.14));background:rgba(255,255,255,.04);color:inherit;border-radius:12px;padding:9px 4px;font:700 15px/1.2 var(--body,system-ui);cursor:pointer;transition:background .14s,border-color .14s}
.howto .langs button.on{background:var(--paper,#F5F7FF);color:var(--ink,#0D1122);border-color:var(--paper,#F5F7FF)}
.howto .body{overflow-y:auto;padding:2px 20px 18px;overscroll-behavior:contain}
.howto .body h3{font-size:17px;font-weight:800;letter-spacing:0;margin:18px 0 8px;font-family:inherit;color:var(--gold,#FFC83D)}
.howto .body ol{margin:0;padding:0;list-style:none;display:grid;gap:10px;counter-reset:s}
.howto .body li{position:relative;padding-inline-start:36px;font-size:15.5px;line-height:1.55;color:rgba(244,246,255,.92)}
.howto .body ol.steps li::before{counter-increment:s;content:counter(s);position:absolute;inset-inline-start:0;top:1px;width:26px;height:26px;border-radius:50%;background:var(--lantern,#FF3E78);color:var(--on-lantern,#fff);font:800 13px/26px var(--body,system-ui);text-align:center}
.howto .body ol.bullets li::before{content:"";position:absolute;inset-inline-start:9px;top:.62em;width:8px;height:8px;border-radius:50%;background:var(--gold,#FFC83D)}
.howto .body[dir=rtl] li{font-size:17px}
.howto .body.ur li{line-height:2.25;font-size:17px}
.howto .body.ur h3{line-height:2}
.howto footer{padding:10px 18px calc(14px + env(safe-area-inset-bottom,0px));border-top:1px solid var(--line,rgba(255,255,255,.1))}
.howto footer button{width:100%;border:0;border-radius:999px;padding:13px;background:var(--lantern,#FF3E78);color:var(--on-lantern,#fff);font:800 16px var(--body,system-ui);cursor:pointer}
@keyframes howtoUp{from{transform:translateY(40px);opacity:0}}
@keyframes howtoFade{from{opacity:0}}
@media (prefers-reduced-motion:reduce){.howto,.howto-scrim{animation:none}}`;
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  const ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4.5"/><path d="M12 17.5h.01"/></svg>';
  const get = () => { try{ return localStorage.getItem("howtoLang") || "en"; }catch(e){ return "en"; } };
  const set = l => { try{ localStorage.setItem("howtoLang", l); }catch(e){} };
  const loaded = {};
  function font(L){
    if(!L.font || loaded[L.id]) return;
    loaded[L.id] = true;
    const l = document.createElement("link"); l.rel = "stylesheet";
    l.href = `https://fonts.googleapis.com/css2?family=${L.font}&display=swap`;
    document.head.appendChild(l);
  }
  function body(game, lang){
    const L = LANGS.find(x=>x.id===lang) || LANGS[0];
    const lines = (T[game]?.[lang] || T[game]?.en || "").split("\n").map(s=>s.trim()).filter(Boolean);
    let html = "", list = [], first = true;
    const flush = () => { if(list.length) html += `<ol class="${first ? "steps" : "bullets"}">${list.map(x=>`<li>${x}</li>`).join("")}</ol>`; list = []; };
    for(const ln of lines){
      if(ln.startsWith("#")){ flush(); first = false; html += `<h3>${ln.slice(1).trim()}</h3>`; }
      else list.push(ln);
    }
    flush();
    return `<div class="body ${L.id}" dir="${L.dir}" lang="${L.id}" style="${L.family ? `font-family:${L.family},system-ui,sans-serif` : ""}">${html}</div>`;
  }
  function open(game){
    close();
    let lang = get();
    const box = document.createElement("div"); box.className = "howto-scrim"; box.id = "howto";
    const draw = () => {
      const L = LANGS.find(x=>x.id===lang) || LANGS[0]; font(L);
      const ui = UI[lang] || UI.en;
      box.innerHTML = `<div class="howto" role="dialog" aria-modal="true" aria-label="${ui.title}">
        <header dir="${L.dir}" style="${L.family ? `font-family:${L.family},system-ui` : ""}"><h2>${ui.title}</h2><button class="x" type="button" aria-label="${ui.close}">×</button></header>
        <div class="langs" role="tablist">${LANGS.map(x=>`<button type="button" role="tab" aria-selected="${x.id===lang}" data-lang="${x.id}" class="${x.id===lang ? "on" : ""}" lang="${x.id}">${x.name}</button>`).join("")}</div>
        ${body(game, lang)}
        <footer><button type="button" class="done" style="${L.family ? `font-family:${L.family},system-ui` : ""}">${ui.close}</button></footer></div>`;
    };
    draw();
    box.onclick = e => {
      const b = e.target.closest("[data-lang]");
      if(b){ lang = b.dataset.lang; set(lang); draw(); return; }
      if(e.target === box || e.target.closest(".x") || e.target.closest(".done")) close();
    };
    document.body.appendChild(box);
    document.documentElement.style.overflow = "hidden";
  }
  function close(){
    const b = document.getElementById("howto");
    if(!b) return false;
    b.remove(); document.documentElement.style.overflow = "";
    return true;
  }
  function button(game, extraStyle=""){
    return `<button type="button" class="howto-btn" data-howto="${game}" style="${extraStyle}">${ICON}How to play <small>English · العربية · اردو · हिन्दी</small></button>`;
  }
  document.addEventListener("click", e => { const b = e.target.closest("[data-howto]"); if(b) open(b.dataset.howto); });
  document.addEventListener("keydown", e => { if(e.key === "Escape") close(); });
  if(window.BackGuard) BackGuard.onBack(close);
  window.HowTo = {button, open, close};
})();
