-- ================================================================
--  REC Bijnor Academic AI Assistant — FAQ Seed Data
--  Source: chatbot_data1.csv (original college data)
--  Run AFTER uvicorn has started so all tables exist
--  Command: psql -U postgres -d chatbot_db -f seed_faqs.sql
-- ================================================================

TRUNCATE TABLE faqs RESTART IDENTITY CASCADE;

INSERT INTO faqs (keyword, response, is_active, created_at) VALUES


-- ════════════════════════════════════════════════════
--  GREETINGS
-- ════════════════════════════════════════════════════

('hello, hlo, hi, hey',
'Hello! 👋 Welcome to the REC Bijnor Academic AI Assistant. I am here to help you with admissions, fees, hostel, courses, faculty, exams, and all college-related queries. How may I assist you today?',
TRUE, NOW()),

('good morning',
'Good morning! ☀️ Hope your day is off to a great start. I am your REC Bijnor AI Assistant — feel free to ask me anything about the college.',
TRUE, NOW()),

('good afternoon',
'Good afternoon! I am your REC Bijnor Academic AI Assistant. How may I help you today?',
TRUE, NOW()),

('good evening',
'Good evening! I am your REC Bijnor Academic AI Assistant, available anytime. What would you like to know?',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  GENERAL RESPONSES
-- ════════════════════════════════════════════════════

('thank you, thanks',
'You are most welcome! 😊 It is always a pleasure to assist you. Feel free to return anytime you have questions about REC Bijnor.',
TRUE, NOW()),

('okay, ok',
'Great! Let me know if you have any more questions. I am always here to help. 👍',
TRUE, NOW()),

('bye, goodbye',
'Goodbye! 👋 Have a wonderful day. Do visit again whenever you need assistance. Best wishes!',
TRUE, NOW()),

('who are you, what are you, introduce yourself',
'I am the official AI-powered Academic Assistant of Rajkiya Engineering College, Bijnor. I am designed to provide accurate and instant information about the college — from admissions and academics to faculty, hostel, placements, and more.',
TRUE, NOW()),

('your name, what is your name',
'I am the REC Bijnor Academic AI Assistant — your intelligent guide for all things related to Rajkiya Engineering College, Bijnor. How can I assist you today?',
TRUE, NOW()),

('help, what can you do, how can you help',
'Sure! I can assist you with a wide range of queries including: Admissions and eligibility, Fee structure, Hostel facilities, Departments and courses, Faculty and subject information, Timetable and academic calendar, Examination schedules and results, Placements, Scholarships, and Campus facilities. Just type your question and I will do my best to help!',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  COLLEGE INFORMATION
-- ════════════════════════════════════════════════════

('college timing, timing, working hours, office hours',
'Rajkiya Engineering College, Bijnor generally operates from 9:00 AM to 5:00 PM on working days. Classes, labs, and the administrative office follow this schedule. The campus remains closed on Sundays and public holidays.',
TRUE, NOW()),

('location, address, where is college, college address',
'Rajkiya Engineering College, Bijnor is located at: Near Eidgah, Dattyana Road, Chandpur (Bijnor) — 246725, Uttar Pradesh, India. The campus is conveniently situated in Chandpur town.',
TRUE, NOW()),

('contact, email, phone, how to contact, reach college',
'You can contact Rajkiya Engineering College, Bijnor at: 📧 Email — info@recb.ac.in | 📍 Address — Near Eidgah, Dattyana Road, Chandpur, Bijnor, Uttar Pradesh — 246725. The administrative office is available Monday to Saturday, 9 AM to 5 PM.',
TRUE, NOW()),

('principal, director, who is principal, college head',
'The Principal of Rajkiya Engineering College, Bijnor provides leadership, academic vision, and administrative guidance across all departments. For official appointments or communications, please reach out to the administrative office during college working hours.',
TRUE, NOW()),

('about college, about rec bijnor, college overview, rec bijnor',
'Rajkiya Engineering College (REC) Bijnor is a government engineering institution affiliated with Dr. A.P.J. Abdul Kalam Technical University (AKTU), Lucknow. It offers B.Tech programs in CSE, IT, ECE, EE, and ME, and is committed to delivering quality technical education with a focus on holistic student development.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  ADMISSIONS
-- ════════════════════════════════════════════════════

('admission, admissions, how to apply, eligibility, apply',
'Admission details for REC Bijnor are available on the official college website. Applications are submitted online through the AKTU/UPSEE admission portal. Eligibility requires passing 10+2 with Physics, Chemistry, and Mathematics. Counselling is merit-based and conducted by AKTU. Visit aktu.ac.in for the latest schedule.',
TRUE, NOW()),

('fees, fee structure, tuition fee, semester fee, how much fees',
'The fee structure at REC Bijnor depends on your branch and semester. For the most accurate and up-to-date fee details, please visit the Fee Section on the official college website or contact the accounts office directly.',
TRUE, NOW()),

('scholarship, scholarships, financial aid',
'Scholarships at REC Bijnor are available under various government schemes including UP Government Pre/Post Matric Scholarships, SC/ST fee waivers, and merit-based awards. Applications are processed through the college administration and the UP Scholarship portal at scholarship.up.gov.in.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  DEPARTMENTS & COURSES
-- ════════════════════════════════════════════════════

('departments, branches, courses, which branches, available courses',
'Rajkiya Engineering College, Bijnor offers B.Tech programs in the following departments: Computer Science and Engineering (CSE), Information Technology (IT), Electronics and Communication Engineering (ECE), Electrical Engineering (EE), and Mechanical Engineering (ME). All programs are 4 years (8 semesters), affiliated with AKTU Lucknow.',
TRUE, NOW()),

('semesters, how many semesters, duration, b.tech duration',
'The B.Tech program at REC Bijnor spans 4 years, divided into 8 semesters. Each semester is approximately 6 months in duration. Examinations are conducted by AKTU, Lucknow at the end of each semester.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  FACULTY (GENERAL)
-- ════════════════════════════════════════════════════

('faculty, teachers, professors, teaching staff',
'REC Bijnor is proud to have experienced, qualified, and dedicated faculty members across all its departments. Each subject is handled by a specialist faculty. For department-wise faculty details, please refer to the college website or contact your respective department office.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  SEMESTER-WISE SUBJECTS & FACULTY (IT/CSE)
-- ════════════════════════════════════════════════════

('1st semester, first semester, sem 1, first sem subjects',
'Subjects in the 1st Semester (IT/CSE) at REC Bijnor are:
  • Engineering Chemistry — Dr. Subia Ambreen Ma''am
  • Engineering Mathematics-I — Dr. Pravesh Kumar Sir
  • Fundamentals of Electrical Engineering — Dr. Navneet Kumar Sir
  • Programming for Problem Solving — Dr. Sudhir Goswami Sir
  • Environmental Studies and Ecology',
TRUE, NOW()),

('2nd semester, second semester, sem 2, second sem subjects',
'Subjects in the 2nd Semester (IT/CSE) at REC Bijnor are:
  • Engineering Physics — Dr. Hemant Kumar Sir
  • Engineering Mathematics-II — Dr. Pravesh Kumar Sir
  • Fundamentals of Electronics Engineering — Dr. Parvesh Kumar Sir
  • Fundamentals of Mechanical Engineering — Dr. Rohitash Sir
  • Soft Skills — Dr. Ashu Tomar Ma''am',
TRUE, NOW()),

('3rd semester, third semester, sem 3, third sem subjects',
'Subjects in the 3rd Semester (IT/CSE) at REC Bijnor are:
  • Electronics Engineering — Dr. Parvesh Kumar Sir
  • Technical Communication — Dr. Ashu Tomar Ma''am
  • Data Structures — Dr. Sudhir Goswami Sir
  • Computer Organization and Architecture — Nakul Chahal Sir
  • Discrete Structures and Theory of Logic — Dr. Santosh Kumar Sir
  • Python Programming — Dr. Ishan Bhardwaj Sir',
TRUE, NOW()),

('4th semester, fourth semester, sem 4, fourth sem subjects',
'Subjects in the 4th Semester (IT/CSE) at REC Bijnor are:
  • Mathematics-IV — Dr. Pravesh Kumar Sir
  • Universal Human Values and Professional Ethics — Prabhat Sir
  • Operating System — Dr. Vivek Jaiswal Sir
  • Theory of Automata and Formal Languages — Dr. Sudhir Goswami Sir
  • Object Oriented Programming with Java — Nakul Chahal Sir
  • Cyber Security — Dr. Pushp Maheshwari Sir',
TRUE, NOW()),

('5th semester, fifth semester, sem 5, fifth sem subjects',
'Subjects in the 5th Semester (IT/CSE) at REC Bijnor are:
  • Database Management System — Dr. Vivek Jaiswal Sir
  • Web Technology — Nakul Chahal Sir
  • Design and Analysis of Algorithms — Dr. Pushp Maheshwari Sir
  • Compiler Design — Nakul Chahal Sir
  • Image Processing — Dr. Ishan Bhardwaj Sir',
TRUE, NOW()),

('6th semester, sixth semester, sem 6, sixth sem subjects',
'Subjects in the 6th Semester (IT/CSE) at REC Bijnor are:
  • Software Engineering — Dr. Vivek Jaiswal Sir
  • Data Analytics — Nakul Chahal Sir
  • Computer Networks — Dr. Santosh Kumar Sir
  • Blockchain Architecture Design — Dr. Ishan Bhardwaj Sir
  • Idea to Business Model — Dr. Paritosh Sharma Sir',
TRUE, NOW()),

('7th semester, seventh semester, sem 7, seventh sem subjects',
'Subjects in the 7th Semester (IT/CSE) at REC Bijnor are:
  • Artificial Intelligence — Nakul Chahal Sir
  • Internet of Things (IoT) — Dr. Santosh Kumar Sir
  • Project Management — Dr. Paritosh Sharma Sir',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  FACULTY — INDIVIDUAL QUERIES
-- ════════════════════════════════════════════════════

('dr subia ambreen, subia maam, chemistry teacher, engineering chemistry',
'Dr. Subia Ambreen Ma''am teaches Engineering Chemistry in the 1st Semester (IT/CSE) at REC Bijnor.',
TRUE, NOW()),

('dr pravesh kumar, pravesh sir, mathematics teacher, maths faculty',
'Dr. Pravesh Kumar Sir teaches Engineering Mathematics at REC Bijnor. He handles Mathematics-I (1st Sem), Mathematics-II (2nd Sem), and Mathematics-IV (4th Sem) for the IT/CSE department.',
TRUE, NOW()),

('dr navneet kumar, navneet sir, electrical engineering teacher',
'Dr. Navneet Kumar Sir teaches Fundamentals of Electrical Engineering in the 1st Semester at REC Bijnor.',
TRUE, NOW()),

('dr sudhir goswami, sudhir sir, programming teacher, data structure teacher, automata teacher',
'Dr. Sudhir Goswami Sir teaches Programming for Problem Solving (1st Sem), Data Structures (3rd Sem), and Theory of Automata and Formal Languages (4th Sem) in the IT/CSE department.',
TRUE, NOW()),

('dr hemant kumar, hemant sir, physics teacher, engineering physics',
'Dr. Hemant Kumar Sir teaches Engineering Physics in the 2nd Semester for the IT/CSE department at REC Bijnor.',
TRUE, NOW()),

('dr parvesh kumar, parvesh sir, electronics teacher',
'Dr. Parvesh Kumar Sir teaches Fundamentals of Electronics Engineering (2nd Sem) and Electronics Engineering (3rd Sem) in the IT/CSE department at REC Bijnor.',
TRUE, NOW()),

('dr rohitash, rohitash sir, mechanical teacher',
'Dr. Rohitash Sir teaches Fundamentals of Mechanical Engineering in the 2nd Semester at REC Bijnor.',
TRUE, NOW()),

('dr ashu tomar, ashu maam, soft skills teacher, communication teacher',
'Dr. Ashu Tomar Ma''am teaches Soft Skills (2nd Sem) and Technical Communication (3rd Sem) in the IT/CSE department at REC Bijnor.',
TRUE, NOW()),

('nakul chahal, nakul sir, java teacher, web technology teacher, ai teacher, compiler teacher',
'Nakul Chahal Sir is one of the core faculty members in the IT/CSE department. He teaches: Computer Organization and Architecture (3rd Sem), OOP with Java (4th Sem), Web Technology (5th Sem), Compiler Design (5th Sem), Data Analytics (6th Sem), and Artificial Intelligence (7th Sem).',
TRUE, NOW()),

('dr santosh kumar, santosh sir, networks teacher, iot teacher, discrete structures',
'Dr. Santosh Kumar Sir teaches Discrete Structures and Theory of Logic (3rd Sem), Computer Networks (6th Sem), and Internet of Things (7th Sem) at REC Bijnor.',
TRUE, NOW()),

('dr ishan bhardwaj, ishan sir, python teacher, image processing teacher, blockchain teacher',
'Dr. Ishan Bhardwaj Sir teaches Python Programming (3rd Sem), Image Processing (5th Sem), and Blockchain Architecture Design (6th Sem) in the IT/CSE department at REC Bijnor.',
TRUE, NOW()),

('prabhat sir, ethics teacher, human values teacher',
'Prabhat Sir teaches Universal Human Values and Professional Ethics in the 4th Semester at REC Bijnor.',
TRUE, NOW()),

('dr vivek jaiswal, vivek sir, os teacher, dbms teacher, software engineering teacher',
'Dr. Vivek Jaiswal Sir teaches Operating System (4th Sem), Database Management System (5th Sem), and Software Engineering (6th Sem) in the IT/CSE department at REC Bijnor.',
TRUE, NOW()),

('dr pushp maheshwari, pushp sir, cyber security teacher, algorithm teacher',
'Dr. Pushp Maheshwari Sir teaches Cyber Security (4th Sem) and Design and Analysis of Algorithms (5th Sem) at REC Bijnor.',
TRUE, NOW()),

('dr paritosh sharma, paritosh sir, business model teacher, project management teacher',
'Dr. Paritosh Sharma Sir teaches Idea to Business Model (6th Sem) and Project Management (7th Sem) at REC Bijnor.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  ACADEMICS
-- ════════════════════════════════════════════════════

('timetable, time table, class schedule',
'Class timetables are displayed on department notice boards and published on the official college website at the start of each semester. Contact your class coordinator or department office for the latest schedule.',
TRUE, NOW()),

('academic calendar, calendar, important dates',
'The academic calendar is released at the beginning of each academic year. It includes semester dates, examination schedules, holidays, and key events. Check the official college website or department notice boards for the current calendar.',
TRUE, NOW()),

('exam, exams, examination, exam schedule',
'Examination schedules and results are published on both the AKTU portal (aktu.ac.in) and the official college portal. Semester-end exams are conducted by AKTU, while internal and sessional exams are held by the college mid-semester.',
TRUE, NOW()),

('result, results, marksheet, how to check result',
'Results are declared online through the official AKTU student portal at aktu.ac.in. Log in with your enrollment number to view results, download marksheets, and access grade cards.',
TRUE, NOW()),

('attendance, attendance rule, minimum attendance, percentage',
'Students must maintain a minimum of 75% attendance in each subject to be eligible for semester examinations. Attendance records are updated by faculty and can be reviewed through the college ERP or notice boards.',
TRUE, NOW()),

('backlog, back paper, failed subject, arrear',
'Students with backlogs can register for the AKTU back paper examination through the official portal before the deadline. It is advised to clear backlogs at the earliest to avoid complications in graduation.',
TRUE, NOW()),

('syllabus, curriculum, subject list',
'The B.Tech syllabus is prescribed by AKTU, Lucknow and can be downloaded from aktu.ac.in under the Academics section. Department offices also maintain printed copies of the current syllabus for student reference.',
TRUE, NOW()),

('internship, industrial training, summer training',
'Industrial training or internship is a mandatory part of the B.Tech program, typically required after the 3rd or 5th semester. Duration is generally 4 to 8 weeks. Students may arrange placements independently or through the Training and Placement Cell.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  CAMPUS FACILITIES
-- ════════════════════════════════════════════════════

('hostel, accommodation, boys hostel, girls hostel, stay',
'REC Bijnor provides separate hostel facilities for boys and girls with proper amenities and Wi-Fi connectivity. Hostel allotment is conducted at the beginning of the academic year. Contact the hostel warden or admission office for current availability and fee details.',
TRUE, NOW()),

('library, books, library hours, e-resources',
'The college library houses a large collection of academic books, research journals, and e-resources. Library timings are generally 9:00 AM to 5:00 PM on working days. Students can borrow books using their college ID card.',
TRUE, NOW()),

('canteen, food, cafeteria',
'There is a canteen on the REC Bijnor campus. However, it may remain closed at certain times. For the current operational status and further queries regarding the canteen or mess facility, please contact the Dean of Student Welfare.',
TRUE, NOW()),

('wifi, internet, campus wifi',
'Wi-Fi connectivity is available across the REC Bijnor campus including academic blocks and hostels. Students can connect using their college login credentials. For technical issues, contact the IT support department.',
TRUE, NOW()),

('lab, laboratory, computer lab, practical facility',
'REC Bijnor has well-equipped laboratories for all departments including Computer Labs, Electronics Lab, Communication Lab, Electrical Lab, and Mechanical Workshop. Labs are accessible during scheduled practical sessions.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  PLACEMENTS
-- ════════════════════════════════════════════════════

('placement, placements, campus placement, job, recruitment',
'The Training and Placement Cell at REC Bijnor actively facilitates campus recruitment drives, helping students get placed in reputed companies. All eligible students are registered through the T&P Cell. Watch notice boards and the official website for upcoming drive announcements.',
TRUE, NOW()),

('companies, recruiters, which companies visit, top companies',
'Several reputed companies recruit from REC Bijnor including TCS, Infosys, Wipro, HCL, Tech Mahindra, Capgemini, and various core sector firms. The recruiter base grows every year. Contact the T&P Cell for the latest placement report.',
TRUE, NOW()),

('package, salary, ctc, average package',
'The average placement package at REC Bijnor ranges from Rs. 3 to 6 LPA, with top offers going up to Rs. 8 to 15 LPA depending on the company and branch. For verified and updated figures, contact the Training and Placement Cell.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  EVENTS & ACTIVITIES
-- ════════════════════════════════════════════════════

('fest, festival, techfest, cultural fest, annual fest',
'REC Bijnor hosts an annual technical and cultural fest that encourages innovation, creativity, and talent among students. Events include paper presentations, coding contests, project showcases, cultural performances, and sports competitions.',
TRUE, NOW()),

('club, clubs, student clubs, coding club',
'REC Bijnor has active student clubs including Coding Club, Robotics Club, Cultural Club, and NSS. These clubs organize workshops, competitions, and events throughout the year. Join through your department coordinator or during semester registration.',
TRUE, NOW()),


-- ════════════════════════════════════════════════════
--  AKTU & CERTIFICATES
-- ════════════════════════════════════════════════════

('aktu, university, affiliated university, dr apj',
'Rajkiya Engineering College, Bijnor is affiliated with Dr. A.P.J. Abdul Kalam Technical University (AKTU), Lucknow. All semester examinations, results, degree certificates, and academic regulations are governed by AKTU. Visit aktu.ac.in for university-level services.',
TRUE, NOW()),

('degree, b.tech degree, graduation, final certificate',
'B.Tech degree certificates are issued by AKTU after successful completion of all 8 semesters and clearance of all backlogs. Apply for your provisional certificate through the AKTU portal once final results are declared.',
TRUE, NOW()),

('migration certificate, character certificate, bonafide',
'Migration, Character, and Bonafide Certificates are issued by the college administrative office. Submit a written application with your college ID card. Processing generally takes 3 to 5 working days.',
TRUE, NOW());


-- ════════════════════════════════════════════════════
--  VERIFY
-- ════════════════════════════════════════════════════
SELECT COUNT(*) AS total_faqs_inserted FROM faqs;
SELECT id, LEFT(keyword, 55) AS keyword_preview FROM faqs ORDER BY id;