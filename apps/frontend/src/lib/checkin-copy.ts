export const CHECKIN_OPENING =
  "Hi Mdm Tan! It's Nomi checking in 😊 How are you feeling right now? Reply with a number from 1 (low) to 5 (good), or a short note.";
export const CHECKIN_FOLLOW_UP_1 =
  "Thanks for sharing. How are you feeling compared with this morning — same, better, or worse? 🌿";
export const CHECKIN_FOLLOW_UP_2 =
  "Is there anything you need help with today? 🙏";
export const CHECKIN_THANK_YOU = "Thank you, I've noted this. Take care 💚";

export type CheckinReply = { from: "nomi" | "senior"; text: string };

export function buildCheckinThread(
  seniorReplies: [string, string, string],
): CheckinReply[] {
  return [
    { from: "nomi", text: CHECKIN_OPENING },
    { from: "senior", text: seniorReplies[0] },
    { from: "nomi", text: CHECKIN_FOLLOW_UP_1 },
    { from: "senior", text: seniorReplies[1] },
    { from: "nomi", text: CHECKIN_FOLLOW_UP_2 },
    { from: "senior", text: seniorReplies[2] },
    { from: "nomi", text: CHECKIN_THANK_YOU },
  ];
}
