---
title: "Home"
date: 2023-10-24
type: landing

design:
  spacing: "6rem"

sections:
  - block: hero
    content:
      announcement:
        badge:
          text: NEW
          color: primary
        text: "We are recruiting students and interns."
        link:
          text: "Apply"
          url: "/join/"

      title: |-
        ManuFuture Laboratory
        @ Hanyang University

      text: "한양대학교 미래제조 연구실"

    design:
      spacing:
        padding: [0, 0, 0, 0]
        margin: [0, 0, 0, 0]
      css_class: "dark whitespace-pre-line mfl-hero"
      background:
        color: "#0a0e27"
        gradient:
          type: radial
          start: "rgba(124,58,237,0.45)"
          end: "transparent"
          position: "50% -10%"
          shape: ellipse
          size: "80% 80%"
        gradient_mesh:
          enable: true
          style: orbs
          intensity: medium
          animation: pulse
          colors: ["primary-500/25", "secondary-500/25"]
          orb_count: 2
          positions: ["top-1/3 left-1/4", "bottom-1/3 right-1/4"]
          sizes: ["w-[32rem] h-[32rem]", "w-[26rem] h-[26rem]"]

  - block: markdown
    id: intro
    content:
      title: ""
      text: |
        Welcome to the ManuFuture Laboratory at Hanyang University, led by Prof. Sukkyung Kang. Our laboratory explores future manufacturing technologies at the intersection of advanced materials processing, surface and interface engineering, precision manufacturing, and data-driven process innovation. We aim to develop scientific understanding and practical engineering solutions for sustainable, intelligent, and high-performance manufacturing systems.

        We are always looking for motivated students and collaborators interested in shaping the future of manufacturing. [Join us →](/join/)

    design:
      spacing:
        padding: ["3rem", 0, "2rem", 0]
---
