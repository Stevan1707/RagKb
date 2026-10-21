SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS citation;
DROP TABLE IF EXISTS message;
DROP TABLE IF EXISTS conversation;
DROP TABLE IF EXISTS chunk;
DROP TABLE IF EXISTS document;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE document (
  id           INT UNSIGNED AUTO_INCREMENT,
  filename     VARCHAR(255) NOT NULL COMMENT '原始文件名',
  path         VARCHAR(500) NOT NULL COMMENT '落盘路径',
  status       VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending/processing/done/failed',
  chunk_count  INT          NOT NULL DEFAULT 0 COMMENT '切出的块数',
  error        VARCHAR(500) DEFAULT NULL COMMENT '失败原因',
  created_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_created (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='上传的文档';

CREATE TABLE chunk (
  id      BIGINT UNSIGNED AUTO_INCREMENT COMMENT '与 FAISS 向量 id 一致',
  doc_id  INT UNSIGNED NOT NULL,
  page    INT NOT NULL DEFAULT 1 COMMENT '页码，从 1 起',
  seq     INT NOT NULL COMMENT '文档内块序号，从 0 起',
  content MEDIUMTEXT NOT NULL COMMENT '块原文',
  PRIMARY KEY (id),
  UNIQUE KEY uk_doc_seq (doc_id, seq),
  KEY idx_doc (doc_id),
  CONSTRAINT fk_chunk_doc FOREIGN KEY (doc_id) REFERENCES document(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文本块';

CREATE TABLE conversation (
  id           INT UNSIGNED AUTO_INCREMENT,
  title        VARCHAR(255) NOT NULL,
  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_updated (updated_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话';

CREATE TABLE message (
  id              BIGINT UNSIGNED AUTO_INCREMENT,
  conversation_id INT UNSIGNED NOT NULL,
  role            ENUM('user','assistant') NOT NULL,
  content         MEDIUMTEXT NOT NULL,
  status          VARCHAR(20) NOT NULL DEFAULT 'done' COMMENT 'streaming/done/stopped/failed',
  created_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_conv (conversation_id, id),
  CONSTRAINT fk_msg_conv FOREIGN KEY (conversation_id) REFERENCES conversation(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息';

CREATE TABLE citation (
  id         BIGINT UNSIGNED AUTO_INCREMENT,
  message_id BIGINT UNSIGNED NOT NULL,
  chunk_id   BIGINT UNSIGNED NOT NULL,
  rank_no    SMALLINT UNSIGNED NOT NULL COMMENT '对应正文 [1][2]，从 1 起',
  score      FLOAT DEFAULT NULL COMMENT '检索得分，用于评估',
  PRIMARY KEY (id),
  UNIQUE KEY uk_msg_rank (message_id, rank_no),
  KEY idx_chunk (chunk_id),
  CONSTRAINT fk_cit_msg   FOREIGN KEY (message_id) REFERENCES message(id)  ON DELETE CASCADE,
  CONSTRAINT fk_cit_chunk FOREIGN KEY (chunk_id)   REFERENCES chunk(id)    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='答案与片段的引用关系';