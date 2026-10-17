// 옥스 알림 받기 (웹 푸시). 누르면 해당 화면으로.
self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(data.title || "옥스", {
      body: data.body || "",
      data: { link: data.link || "/home" },
      tag: data.tag,
    }),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.link));
});
