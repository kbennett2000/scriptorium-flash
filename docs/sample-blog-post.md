# Scriptorium
### Moving a real app to Runpod Flash, with receipts

On August 18th, my app read *Treasure Island*, decided which ninety-one moments deserved a painting, painted them on rented graphics cards, and handed me a bill for forty-three cents.

This is the story of moving a real application onto Runpod Flash. Not a hello-world: an app I actually use, with opinions and custom code and a pipeline that breaks if you look at it wrong. I kept every receipt. Every number in this post lives in one file in the public repo, and a checking program verifies the repo's figures with no internet connection. If it isn't in the log, it isn't in this post.

## The starting point

Scriptorium is my book-illustration app. You hand it a book (any book) and it reads the text, figures out who the characters are, picks the scenes worth a picture, paints them in a chosen art style, and packages everything as an offline book you can read on your phone.

Until this month, all of it ran on the one RTX 5070 in my office. The text analysis, the image painting, and the coordination between them took turns on the same chip. A full run on my standard test story took **388.63 seconds**, about six and a half minutes. Hold that number. It turns out to have been my computer on its best day, and the proof of that is my favorite part of this story.

This setup matters because it isn't unusual. It's how most developers start: one machine, one graphics card, at home. And a growing suspicion that the cloud is either the answer or a trap.

## The decision rule

The first real question wasn't "how do I use Runpod." It was "which parts of my app even belong there." I ended up with a rule I'd now give anyone:

**Your own custom code goes in a Flash app. A commodity model job goes to a ready-made hosted endpoint. Cheap coordination work stays wherever it already lives.**

For Scriptorium that meant three different answers. The painting pipeline is my code doing something specific to my app. It became a Flash app I own. The text analysis is a standard job any language model can do. I tried Runpod's ready-made hosted models, and what happened there gets its own section. The coordination barely uses any computing power, so it stayed home, because moving it buys nothing.

## A declaration becomes a fleet

Here's the heart of the Flash app, excerpted from the repo:

```python
# flash-imagegen/app.py — excerpt
from runpod_flash import Endpoint, GpuType

imagegen = Endpoint(
    name="scriptorium-imagegen",
    image=IMAGE,        # ComfyUI + models baked in: 17.66 GB, private
    gpu=GpuType.NVIDIA_GEFORCE_RTX_4090,  # pinned to one exact card
    workers=(0, 4),     # scale to zero, fan out to four
    idle_timeout=60,
    flashboot=True,
)
```

It's a plain description written in Python: here's my app, here's the exact graphics card I want, here's how the fleet should behave. The `workers=(0, 4)` line says: when nobody needs pictures, run zero machines, so I pay nothing; when a book needs a batch, wake up as many as four and split the work.

One honest warning for anyone who tries this. My models are eleven-plus gigabytes, so the app ships as a container (a bundled package of my software and models) rather than a small uploaded function. For apps packaged that way, the command you would guess, `flash deploy`, prints "success" and creates **nothing**. I filed that as [flash#365](https://github.com/runpod/flash/issues/365). The repo ships the small script that provisions it correctly.

Did the move change my app's output? I had the cloud redraw pictures my home machine had already made, and compared them: **0 of 1,011,712 pixels differ** across all nine test plates. Same renderer, different building.

## What the stopwatch said

The honest headline: **388.63 seconds at home, 325.24 hybrid.** And the part a sales page would hide: the faster run also happened to produce 18 pictures against home's 16. The app decides how many scenes deserve a picture, and that varies run to run. I show the raw times unadjusted.

Where the render saving came from: **72 percent of it is that the rented card is simply faster than mine. 28 percent came from painting pictures in parallel.** I'm not going to pretend the clever part did the work.

Per picture, with the accounting stated: my home card takes **7.595 seconds**. The rented RTX 4090 takes **4.7725 seconds** by the bake median (the conservative number, because it includes two renders where the model had to load from cold) and **4.2790 seconds** warmed up. Call it **1.59×** by the strict count, 1.78× card-to-card. Cost: **$0.001742 per picture**, about a sixth of a penny.

And there's a roadmap hiding in the arithmetic: if painting took *zero* seconds, a run would still take **251.5 seconds**, because text analysis and coordination are **74 percent** of the time. So I know exactly what moves next.

## The finding I didn't go looking for

While measuring my home baseline, the numbers stopped making sense: one text step was taking anywhere from 26 seconds to two and a half minutes, when it should take about two and a half.

The cause: a desktop AI-art tool I'd left open was quietly holding my graphics card. My text model needed 6.19 gigabytes of the card's memory and was getting **0.13**. The rest had spilled onto the regular processor, which is terrible at this work. I closed the other program: right back to about two seconds.

Do the comparison that matters. Sharing my card cost me up to **37×** on text steps. Renting a faster card bought me **1.59×** on renders. Put those side by side and the third thing serverless sells becomes visible. Not speed, not scale, but **isolation**: a rented worker is never fighting your browser, your art tool, or anything else for the card. On this evidence, isolation was worth more than the silicon.

It also proves the claim from the top: my 388.63-second home baseline was a best case, measured on a machine that happened to be behaving.

## Cold starts, honestly

If the whole fleet has gone to sleep, the first request waits **489.82 seconds** (about eight minutes) and **478.2** of those are Runpod pulling my 17.7-gigabyte container onto a fresh machine and starting the worker. Two mercies: the pull time is **not billed**, and once one machine is awake, the next picture takes about **five seconds**. So the practice is simple: wake the fleet before you need it.

One more thing I have to report both halves of. I asked for zero standby machines, and Flash deploys one anyway. You can't remove it. That's a bug, and I filed it ([flash#364](https://github.com/runpod/flash/issues/364)). But I also measured that standby machine across three idle hours, and it billed **exactly $0.0000000000**. So the same defect that's a surprise in the docs is free warm-up insurance in practice. Both halves are true, which is exactly why it's filed.

## The text steps stayed home, and the reason matters

My pipeline doesn't read model answers like a person. A program reads them, so every answer has to arrive in an exact fill-in-the-blanks form: JSON, checked against a schema, a written specification of which fields must appear and what's allowed in them.

At home I can *force* that. My local serving software supports constrained decoding. It physically restricts what the model is able to type, so an invalid reply is impossible by construction.

On Runpod's hosted models, across two models and every call I made: **not one clean parse.** One model spent its entire answer allowance thinking to itself. I paid, and no answer arrived. The capability to force the format does exist on some of their endpoints (the standard `response_format` request field), but it appears in none of their documentation, and it rejects one thing my schemas require: minimum and maximum lengths on text fields. A scene description has to be long enough to paint from and short enough to fit a prompt; strip the limits and a reply can pass the format check while failing the job.

So the verdict I put on a slide: **moving text is not a URL swap.** It's about a day of honest engineering: a check-and-retry layer on my side, handling for models that think before they answer, and fallback model choices, since the catalog moved under me during a five-day project. That day of work is episode two, and I'd argue the finding was worth more than the migration.

## Friction, filed

Most of what I hit rhymes. The pattern, in one sentence: **the tooling reports an intention as an outcome.** Deploy says success: nothing was created. Delete says deleted: the endpoint keeps running, and keeps billing.

I filed seven issues across three Runpod repositories, every one public, every one with reproduction steps:

- [flash#363](https://github.com/runpod/flash/issues/363): two CLIs share one credential file and read it differently
- [flash#364](https://github.com/runpod/flash/issues/364): a standby worker you can't remove
- [flash#365](https://github.com/runpod/flash/issues/365): deploy reports success, creates nothing (container apps)
- [flash#366](https://github.com/runpod/flash/issues/366): the GPU list is advisory; a single pin is binding
- [flash#367](https://github.com/runpod/flash/issues/367): "deleted," while the endpoint keeps running and billing
- [docs#800](https://github.com/runpod/docs/issues/800): a required setting for private images, documented nowhere
- [runpodctl#327](https://github.com/runpod/runpodctl/issues/327): the CLI's suggested command puts your key in shell history

Filing is the point. A complaint on Reddit helps nobody; a reproduction an engineer can run in five minutes is how a platform actually gets better.

## What it all cost

**$1.13.** The entire project: every experiment, every mistake, both books. Reconciled against the billing records to ten decimal places. Twice.

*Treasure Island* itself: **$0.43** for 91 pictures. A demo bake of a short story: about **a dime**.

## How this was actually built

Full disclosure, gladly given: I planned this with Claude, and Claude Code, the command-line coding agent, wrote most of the code. My hands-on time was about **five hours**; the volume came from an autonomous build system I run.

The part worth noticing: I built it using **Runpod's own AI kit**: the six instruction packs they publish for coding assistants, plus their MCP server, the piece that lets an assistant look up their docs and act on my account. I read all **97** instruction files before trusting any of it.

Graded honestly: the kit made the start genuinely fast, and the documentation answers were mostly right. It also teaches habits that put a plaintext credential where it doesn't belong. I filed two issues on that. And credit where it's due: their deploy command prints the true request routes for your app, and that output caught a wrong web address **my own documentation** had carried for two days. Their tool told the truth; I hadn't checked mine against it.

## Take the book

The proof of the whole pipeline fits in your pocket. Open **[scriptorium-reader.vercel.app](https://scriptorium-reader.vercel.app)**. That's *Treasure Island*, 134 pages, 91 pictures, generated end to end by this system. Once it loads, it works with the internet off.

Everything else is public at **[github.com/kbennett2000/scriptorium-flash](https://github.com/kbennett2000/scriptorium-flash)**:
the code, the getting-started guide, the demo runbook, the findings log, the numbers file, and the checker that keeps this post honest.

Episode two is the text migration: same app, same method, same receipts. The question it has to answer is already written down: what's the retry rate when you move from preventing bad answers to inspecting for them? I'll publish the number either way. That's the whole approach: build real things, publish honest accounts, count everything.