package agent.authz

default allow = false

allow if {
  input.action == "read_file"
}

allow if {
  input.action == "create_pr"
  input.time >= "09:00"
  input.time <= "18:00"
}

deny if {
  input.action == "delete_file"
}