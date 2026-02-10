# EVOVE
A tool for behavior research and personal development.

It models real-world activity through a few core objects.
Actions are what you do. Attributes summarize long-term focus areas.
Tags describe actions and attributes to connect related behavior.
Parameters and statuses track internal state and conditions over time.

**Commands**
Objects:
- `8` → `attr`
- `5` → `action`
- `6` → `param`
- `4` → `status`
- `1` → `tag`
- `3` → `shop_item`
- `7` → `log`
- `47` → `sequence`

Interactions:
- `2` → `add`
- `1` → `act`
- `0` → `delete`

Single commands:
- `93` → `list_shop`
- `94` → `list_statuses`
- `25` → `create_action`
- `28` → `create_attr`
- `24` → `create_status`
- `21` → `create_tag`
- `26` → `create_param`
- `91` → `list_tags`
- `98` → `list_attr`
- `95` → `list_actions`
- `96` → `list_params`
- `27` → `add_log`
- `97` → `list_logs`
- `995` → `list_actions_detailed`
- `996` → `list_params_full`
- `998` → `list_attributes_detailed`
- `991` → `list_tags_detailed`
- `994` → `list_active_statuses`
- `999` → `show_user_info`
- `997` → `list_days`
- `07` → `drop_log`
- `007` → `drop_day`
- `71` → `wake`
- `70` → `sleep`
- `770` → `nap`
- `247` → `new_sequence`
- `947` → `list_sequences`
- `047` → `drop_sequence`
- `005` → `drop_actions`
- `008` → `drop_attr`
- `006` → `drop_params`

Command phrases:
- `attr add action`
- `action act`
- `delete attr`
- `delete action`
- `delete status`
- `delete param`
- `add add attr`
- `attr add attr`
- `status add`
- `status act`
- `param act act`
- `param add status`
- `action add tag`
- `param add tag`
- `shop_item add action`
- `shop_item act`
- `action delete`
- `attr delete`
- `param delete`
- `status delete`
