# UdaanHer Saathi — Full Detailed Feature List

*From Learning to Earning*

Every feature below follows the same structure: **What it does**, **How it works**, **What the user experiences**, **Why it matters**.

---

## 1. Onboarding & Access

### 1.1 Language Selection
- **What it does:** Lets the user pick her preferred local language at the very start.
- **How it works:** A simple voice + icon menu of supported languages; no text-reading required to choose.
- **User experience:** She hears a greeting, sees a few icons/flags, and taps or speaks her language.
- **Why it matters:** Removes the very first barrier — most kiosks assume English or a national language by default.

### 1.2 Voice-First Interaction
- **What it does:** Runs the entire kiosk experience through speech instead of text.
- **How it works:** Speech-to-text captures her responses; text-to-speech reads prompts, instructions, and content back to her.
- **User experience:** She talks to the kiosk like a conversation, with icons/visuals as backup, not the primary interface.
- **Why it matters:** Makes the system usable for non-literate and semi-literate users, who are otherwise excluded by default.

### 1.3 Registration & Profile Creation
- **What it does:** Creates a persistent personal profile tied to the user.
- **How it works:** A short voice-guided Q&A captures name, location, and basic details; profile is stored for future visits.
- **User experience:** Feels like a quick, friendly intro conversation, not a form.
- **Why it matters:** Lets her leave and come back without starting over, and lets the system build a history of her progress.

---

## 2. Assessment & Personalization

### 2.1 Adaptive Literacy Detection
- **What it does:** Gauges how literate and digitally comfortable the user is.
- **How it works:** Analyzes her responses during onboarding (hesitation, request for repeats, how she interacts) to classify her comfort level.
- **User experience:** She doesn't take a "test" — the system quietly adapts the interface (more icons/audio vs. more text/self-navigation) based on how she's already interacting.
- **Why it matters:** One-size-fits-all interfaces fail either the most vulnerable users or bore the more capable ones — this avoids both.

### 2.2 Initial Assessment (Interests & Goals)
- **What it does:** Captures her interests, mobility constraints, available hours, education level, and work preferences.
- **How it works:** A short, conversational voice-based questionnaire.
- **User experience:** Feels like being asked "what do you enjoy, what can you realistically commit to" rather than filling out a form.
- **Why it matters:** Personalization downstream (career suggestions, roadmap) is only as good as this initial picture.

### 2.3 Personalized Career Discovery
- **What it does:** Suggests realistic career paths based on her profile.
- **How it works:** A recommendation engine matches her interests/constraints against known career tracks (beauty, tailoring, childcare, appliance repair, entrepreneurship, home services).
- **User experience:** She's presented with a small, relevant set of options instead of an overwhelming catalogue.
- **Why it matters:** Reduces decision fatigue and points her toward paths she's actually likely to succeed in and stick with.

### 2.4 Personalized Learning Roadmap
- **What it does:** Builds a month-by-month plan toward her chosen career.
- **How it works:** Sequences digital literacy, vocational skill-building, and platform-specific prep into a structured timeline (e.g. Month 1: digital literacy, Month 2: technical skills, Month 3: communication, Month 4: platform readiness, Month 5: employment).
- **User experience:** She sees a simple, visual roadmap of what's next, not an open-ended pile of content.
- **Why it matters:** Converts a vague goal ("get a job") into a concrete, achievable sequence of steps.

---

## 3. Learning & Skill-Building

### 3.1 Digital Literacy Modules
- **What it does:** Teaches foundational digital skills.
- **How it works:** Structured lessons cover smartphone basics, WhatsApp, digital payments, online safety, and general internet use.
- **User experience:** Short, practical lessons she can apply immediately (e.g. sending a WhatsApp message, receiving a payment).
- **Why it matters:** Vocational skill alone isn't enough in a digital-first economy — this closes that gap.

### 3.2 Vocational Skill Modules
- **What it does:** Delivers the actual technical training for her chosen trade.
- **How it works:** Career-specific curriculum (e.g. tailoring techniques, beauty service basics, appliance repair fundamentals) delivered through adapted content.
- **User experience:** Step-by-step skill-building she can follow at her own pace.
- **Why it matters:** This is the core value exchange — the skill she came to learn.

### 3.3 Interactive Practice & Assessments
- **What it does:** Reinforces each module with short quizzes and exercises.
- **How it works:** After each lesson, lightweight, voice-friendly questions or practical prompts check retention.
- **User experience:** Quick, low-pressure checks — not exam-style testing.
- **Why it matters:** Confirms she's actually absorbed the material before moving forward, rather than just "watching and hoping."

### 3.4 Even Minor / Background Feature — Pacing & Repeat Controls
- **What it does:** Lets her repeat, slow down, or replay any instruction or lesson segment.
- **How it works:** A simple voice command or button ("say that again," "repeat") replays the last audio segment.
- **User experience:** She never feels rushed or lost — she controls the pace.
- **Why it matters:** A small feature, but critical for non-literate users who can't just "scroll back" the way a reader would.

---

## 4. AI Content Intelligence

### 4.1 AI-Powered Content Adaptation
- **What it does:** Converts existing educational content into something she can actually use.
- **How it works:** AI summarizes, translates, and simplifies source material (often originally in English or a different register) into her language and comprehension level.
- **User experience:** She hears clear, simplified explanations instead of raw, unadapted source content.
- **Why it matters:** Most existing educational content assumes a literate, English-comfortable learner — this bridges that gap.

### 4.2 Dynamic Curriculum Curation (YouTube Data API)
- **What it does:** Pulls in relevant training videos and material in real time rather than relying on a fixed, pre-loaded library.
- **How it works:** Integrates the YouTube Data API to search, filter, and surface relevant content on the fly, based on her current module and language.
- **User experience:** The content she sees feels current and relevant, not static or outdated.
- **Why it matters:** Avoids the team having to manually source and update every single piece of training content by hand.

### 4.3 Quiz & Exercise Generation
- **What it does:** Automatically generates practice questions and exercises from lesson content.
- **How it works:** AI processes the adapted lesson material and generates comprehension checks aligned to it.
- **User experience:** Practice feels tailored to exactly what she just learned, not generic filler questions.
- **Why it matters:** Scales content creation without requiring a human to write new quizzes for every module and language.

### 4.4 Multi-Agent AI Harness
- **What it does:** Runs the "brain" of the kiosk as multiple specialized AI agents rather than one general-purpose model.
- **How it works:** An orchestration layer routes tasks to the right agent — e.g. one agent for literacy detection, one for career matching, one for interview simulation, one for content adaptation.
- **User experience:** Invisible to her — but results in more accurate, task-specific responses than a single generic model would give.
- **Why it matters:** Specialization improves reliability on each individual task instead of asking one model to do everything reasonably well.

### 4.5 Language & Voice Layer (Sarvam AI)
- **What it does:** Powers the actual speech-to-text and text-to-speech in Indian languages.
- **How it works:** Sarvam AI's APIs handle recognition and generation of speech specifically tuned for Indian languages, rather than a generic global voice API.
- **User experience:** She hears and is understood in her actual language and accent, not a rough approximation.
- **Why it matters:** This is the single feature that makes "voice-first, multilingual" actually work in practice, not just in theory.

### 4.6 Reasoning & Conversation Layer (OpenAI)
- **What it does:** Powers the conversational logic, understanding, and decision-making across the kiosk.
- **How it works:** OpenAI's models handle the "thinking" — interpreting her responses, generating explanations, and driving the mentor/interview conversations.
- **User experience:** Conversations with the kiosk feel coherent and responsive, not scripted or robotic.
- **Why it matters:** This is what makes the personalization and mentoring feel genuinely adaptive rather than a fixed decision tree.

---

## 5. Career-Path Customization

### 5.1 Platform-Specific Learning Pathways
- **What it does:** Adapts training depending on where she's headed — a gig platform, a local business, or self-employment.
- **How it works:** The system tags her chosen path and filters/adjusts subsequent modules accordingly.
- **User experience:** Her training feels tailored to her actual destination, not generic.
- **Why it matters:** Generic training often leaves people under-prepared for the specific expectations of real employers or platforms.

### 5.2 Platform Requirement Intelligence
- **What it does:** Understands and incorporates the real onboarding requirements of specific platforms.
- **How it works:** For a platform like Urban Company, the system factors in known requirements — hygiene standards, certifications, customer service expectations — into her training plan.
- **User experience:** She arrives at onboarding already prepared for what's expected, not surprised by it.
- **Why it matters:** Bridges the gap between "trained" and "actually employable" at a specific real-world platform.

### 5.3 Self-Employment / Entrepreneurship Track
- **What it does:** Prepares users who want to work independently rather than through a platform.
- **How it works:** A separate content branch covers pricing strategy, WhatsApp-based client outreach, and basic bookkeeping.
- **User experience:** She gets practical business skills instead of platform-onboarding content she doesn't need.
- **Why it matters:** Not every woman wants or has access to a platform job — this keeps the system relevant to her either way.

---

## 6. Confidence & Employment Readiness

### 6.1 AI Career Mentor
- **What it does:** Acts as an ongoing guide throughout her journey.
- **How it works:** Tracks her progress across modules, flags skill gaps, and offers encouragement and recommendations.
- **User experience:** Feels like a supportive, consistent presence checking in on her, not just a content delivery system.
- **Why it matters:** Skill-building alone often fails without motivation and accountability — this adds that layer.

### 6.2 Mock Interview Coach
- **What it does:** Runs career-specific interview practice.
- **How it works:** AI conducts a simulated interview relevant to her chosen career (e.g. beauty technician, repair technician, childcare) and evaluates her responses.
- **User experience:** A safe, low-stakes space to practice before facing a real interview.
- **Why it matters:** Interview anxiety and inexperience are common, invisible barriers to employment — this directly addresses that.

### 6.3 Customer Interaction Simulations
- **What it does:** Simulates real workplace social situations.
- **How it works:** AI roleplays scenarios like a difficult customer, a first-time client, a complaint, or a negotiation.
- **User experience:** She practices handling pressure and awkward moments before they happen for real.
- **Why it matters:** Technical skill isn't enough — client-facing confidence is often what determines whether she succeeds on the job.

### 6.4 Employment Readiness Score
- **What it does:** Summarizes her overall readiness in one clear score.
- **How it works:** Combines results from digital literacy, technical skill assessments, mock interviews, and customer simulations into a composite score.
- **User experience:** She sees a simple score plus a few clear strengths and areas to improve — not raw data.
- **Why it matters:** Replaces a vague "completion certificate" with something concrete and credible she (and an employer) can actually trust.

### 6.5 Direct Platform Connection
- **What it does:** Connects her to real work immediately after certification.
- **How it works:** Once she reaches readiness, the system routes her application/profile to the platform or opportunity she selected.
- **User experience:** Certification isn't the end — it leads directly into an actual next step toward income.
- **Why it matters:** This is the step most programs skip — closing the loop from "trained" to "earning."

---

## 7. Progress, Data & Storage

### 7.1 Progress Persistence
- **What it does:** Saves her data across sessions.
- **How it works:** User profile, learning history, and scores are stored and reloaded whenever she returns to any kiosk.
- **User experience:** She can leave and come back without losing progress, even at a different kiosk location.
- **Why it matters:** Rural users often can't commit to long, uninterrupted sessions — this respects that reality.

### 7.2 Stored Data Types (background infrastructure)
- **What it does:** Maintains the underlying records that power personalization.
- **How it works:** Stores user profiles, learning history, assessment scores, behavioral metrics, and career pathway data.
- **User experience:** Invisible to her, but it's what makes the system "remember" her.
- **Why it matters:** Without this, every visit would restart from zero, and no long-term impact could be measured.

---

## 8. Impact Measurement & Research

### 8.1 Behavioral Impact Tracking
- **What it does:** Measures real change in the user over time.
- **How it works:** Captures digital literacy, confidence, and employment awareness before training, then again after, using consistent assessment questions.
- **User experience:** Feels like periodic check-ins, not a research burden.
- **Why it matters:** Lets the project prove impact with data instead of just claiming it.

### 8.2 Comparative Study Design
- **What it does:** Benchmarks UdaanHer Saathi against traditional training methods.
- **How it works:** Compares a group using the kiosk (Group B) against a group using traditional training (Group A) on completion rate, confidence, knowledge, retention, employment readiness, and satisfaction.
- **User experience:** Not user-facing — this is a research/evaluation layer.
- **Why it matters:** Gives the project credible evidence for funders, partners, and academic review, not just anecdotal success stories.

---

## 9. Hardware & Physical Kiosk

### 9.1 Kiosk Device
- **What it does:** The physical touchpoint for the whole experience.
- **How it works:** A tablet or touchscreen laptop housed in a simple, sturdy enclosure.
- **User experience:** A familiar, approachable physical object in a space she already trusts.
- **Why it matters:** Community placement (rather than requiring her own smartphone) removes the device-ownership barrier entirely.

### 9.2 Microphone & Speaker
- **What it does:** Enables the entire voice-first interaction model.
- **How it works:** Standard mic/speaker hardware captures her speech and plays back audio responses.
- **User experience:** She speaks and listens naturally, without touching a screen much at all.
- **Why it matters:** This is the physical enabler of the whole non-literate-friendly design.

### 9.3 Deployment Locations
- **What it does:** Determines where the kiosk physically lives.
- **How it works:** Placed in panchayat offices, NGO centres, schools, community centres, or self-help group hubs.
- **User experience:** She accesses it somewhere she already goes and trusts, not a new or unfamiliar place.
- **Why it matters:** Trust and convenience of location directly affects whether she'll actually show up and keep coming back.

### 9.4 Connectivity
- **What it does:** Governs how the kiosk operates in low-connectivity rural areas.
- **How it works:** Internet connection is treated as optional for some features, with core functions designed to degrade gracefully offline (a still-open design question).
- **User experience:** Ideally, minimal disruption even with patchy rural internet.
- **Why it matters:** Rural connectivity is inconsistent — a system that only works online risks excluding the exact users it's meant for.

---

## 10. Data Sources (Background, Not User-Facing)

### 10.1 Public & Educational Content Sources
- **What it does:** Supplies the raw material the AI adapts into lessons.
- **How it works:** Pulled from a range of publicly available websites and educational platforms.
- **User experience:** Invisible — she only sees the adapted, simplified output.
- **Why it matters:** Avoids needing to create every piece of educational content from scratch.

### 10.2 User-Generated Data (Future Dataset)
- **What it does:** Builds a proprietary dataset over time from actual kiosk usage.
- **How it works:** Assessments, learning progress, quiz results, interview simulations, and readiness scores accumulate as women use the kiosk.
- **User experience:** Invisible to her directly, though it's what improves the system for future users.
- **Why it matters:** Over time, this becomes the project's own dataset for improving personalization — not just relying on external sources indefinitely.

---

*Note: dataset selection, offline functionality, and the final locked AI stack are still open design decisions — this document reflects the current design intent, not a fully finalized build.*
