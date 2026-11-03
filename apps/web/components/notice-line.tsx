"use client";

import { useState } from "react";
import { copy } from "@/lib/copy.ko";

type Notice = { notice_id: number; title: string; body: string };

// 게시 중인 공지 맨 앞 하나를 홈 맨 위에 한 줄로(11/2). 누르면 내용 펼침. 자료는 홈 묶음(/home-feed)에서 받음(11/3).
export function NoticeLine({ notices }: { notices: Notice[] }) {
  const [open, setOpen] = useState(false);
  const n = notices[0];
  if (!n) return null;
  return (
    <button className="notice-line w-full ta-left b-0" onClick={() => setOpen(!open)}>
      <b>{copy.notice.label}</b> {n.title}
      {open && n.body && <span className="d-block mt-8 adm-msg">{n.body}</span>}
    </button>
  );
}
