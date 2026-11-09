export const adoptionLabels: Record<string, string> = {
  pending: "Chờ xử lý", contacted: "Đã liên hệ", approved: "Chờ bàn giao", completed: "Đã bàn giao", rejected: "Không được chọn", withdrawn: "Đã rút",
};
export const lifeLabels: Record<string, string> = { open: "Đang tìm", resolved: "Đã giải quyết", closed: "Đã đóng", expired: "Hết hạn" };

export const auditActionLabels: Record<string, string> = {
  create_post: "Đăng tin", edit: "Chỉnh sửa tin", reveal_contact: "Xem liên hệ",
  report: "Báo cáo tin", handle_report: "Xử lý báo cáo", moderate_approve: "Duyệt tin",
  moderate_reject: "Từ chối tin", moderate_hide: "Gỡ tin", lifecycle_close: "Đóng tin",
  lifecycle_renew: "Làm mới tin", lifecycle_resolve: "Xác nhận tin có kết quả",
  adoption_create: "Gửi hồ sơ nhận nuôi", adoption_contact: "Liên hệ người nhận nuôi",
  adoption_approve: "Chọn người nhận nuôi", adoption_complete: "Xác nhận bàn giao",
  adoption_reject: "Từ chối hồ sơ nhận nuôi", adoption_withdraw: "Rút hồ sơ nhận nuôi",
};
export const auditStatusLabels: Record<string, string> = {
  ...lifeLabels, ...adoptionLabels, approved: "Đã duyệt", pending: "Chờ xử lý",
  rejected: "Đã từ chối", hidden: "Đã gỡ", dismissed: "Đã bỏ qua", action_taken: "Đã xử lý",
};
