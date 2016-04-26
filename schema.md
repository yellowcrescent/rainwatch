## `tinfo` schema mapping

The table below shows the correlation between rainwatch's torrent info schema, and the data models of Deluge and rTorrent.

> __*{var1,var2}__ notation indicates that the parameter is extrapolated from the values contained within the curly braces. __@key__ indicates that the dict key from the matching result set is used, and __@index__ indicates the index within the result tuple is used.

|attr_tinfo             |deluge                 |rtorrent
|-----------------------|-----------------------|--------------------------------------------------
|hash                   |@key                   |d.hash
|name                   |name                   |d.name
|path                   |*{save_path+name}      |d.base_path
|base_path              |*{save_path}           |d.directory_base
|time_added             |time_added             |d.creation_date
|comment                |comment                |-
|message                |message                |d.message
|tracker_status         |tracker_status         |-
|tracker_host           |tracker_host           |*{t.url}
|total_size             |total_size             |d.size_bytes
|completed_size         |total_done             |d.completed_bytes
|progress               |progress               |*{d.completed_bytes/d.size_bytes}
|eta                    |eta                    |*{d.down.rate}
|ratio                  |ratio                  |d.ratio/1000
|uploaded               |total_uploaded         |d.up.total
|downloaded             |all_time_download      |d.down.total
|upload_rate            |upload_payload_rate    |d.up.rate
|download_rate          |download_payload_rate  |d.down.rate
|connected_peers        |num_peers              |d.peers_connected
|connected_seeds        |num_seeds              |d.peers_complete
|total_peers            |total_peers            |-
|total_seeds            |total_seeds            |-
|private                |private                |d.is_private
|state                  |state                  |*{d.complete,d.is_active,d.is_hash_checking,d.state}
|time_active            |active_time            |-
|file_count             |num_files              |d.size_files
|piece_count            |num_pieces             |d.size_chunks
|piece_length           |piece_length           |-
|next_announce          |next_announce          |*{t.activity_time_next-system.time}
|tracker_url            |tracker                |t.url
|files                  |files                  |*{f.multicall}
|files.path             |files.path             |f.path
|files.index            |files.index            |{@index}
|files.offset           |files.offset           |f.offset
|files.size             |files.size             |f.size_bytes
|files.progress         |file_progress[i]       |*{f.completed_chunks/f.size_chunks}
|files.priority         |file_priorities[i]     |f.priority
|trackers               |trackers               |*{t.multicall}
|trackers.fail_count    |trackers.fails         |t.failed_counter
|trackers.success_count |-                      |t.success_counter
|trackers.url           |trackers.url           |t.url
|trackers.type          |*{trackers.url}        |t.type
|trackers.enabled       |{true}                 |t.enabled

