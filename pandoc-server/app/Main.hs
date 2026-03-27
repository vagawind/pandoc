{-# LANGUAGE OverloadedStrings #-}
{-# LANGUAGE ScopedTypeVariables #-}
module Main where

import Network.Wai (Application, responseLBS, strictRequestBody, requestMethod, pathInfo)
import qualified Network.Wai as W
import Network.Wai.Handler.Warp (run)
import Network.Wai.Handler.WebSockets (websocketsOr, defaultConnectionOptions)
import Network.WebSockets (ServerApp, acceptRequest, receiveDataMessage, sendTextData,
                          Connection, DataMessage(Text, Binary))
import qualified Data.ByteString.Lazy as BL
import qualified Data.ByteString.Char8 as B8
import qualified Data.Text as T
import qualified Data.Text.Encoding as TE
import qualified Data.Aeson as A
import Data.Aeson (Value, Object)
import Control.Monad (forever)
import Control.Concurrent (forkIO)
import System.Environment (getArgs)
import Data.Maybe (fromMaybe)
import Data.Default (def)
import Control.Concurrent.Timeout (timeout)

import Text.Pandoc.Server (API, app, Params(..), parseServerOptsFromArgs, ServerOpts(..))

import qualified Network.HTTP.Client as HTTP
import qualified Network.HTTP.Client.TLS as HTTP
import qualified Network.HTTP.Types as HTTP

-- MCP Server implementation
main :: IO ()
main = do
  args <- getArgs
  serverOpts <- parseServerOptsFromArgs args
  putStrLn $ "Starting Pandoc MCP server on port " ++ show (serverPort serverOpts)
  putStrLn $ "  - WebSocket MCP: ws://localhost:" ++ show (serverPort serverOpts)
  putStrLn $ "  - HTTP MCP: http://localhost:" ++ show (serverPort serverOpts) ++ "/mcp"
  putStrLn $ "  - HTTP REST API: http://localhost:" ++ show (serverPort serverOpts) ++ "/convert"
  run (serverPort serverOpts) $ combinedApp serverOpts

combinedApp :: ServerOpts -> Application
combinedApp sopts = \req respond -> do
  let pathInfo = W.pathInfo req
      method = W.requestMethod req
  
  -- Handle WebSocket connections
  if pathInfo == [] && method == "GET" 
     then websocketsOr defaultConnectionOptions wsApp (restApp sopts) req respond
  -- Handle HTTP MCP requests
  else if pathInfo == ["mcp"] && method == "POST"
     then httpMCPApp sopts req respond
  -- Handle all other requests with REST API
  else restApp sopts req respond

-- HTTP REST API application (existing app)
restApp :: ServerOpts -> Application
restApp sopts = timeout (serverTimeout sopts) app

-- HTTP MCP application
httpMCPApp :: ServerOpts -> Application
httpMCPApp sopts req respond = do
  body <- W.strictRequestBody req
  case A.eitherDecode body of
    Left err -> do
      putStrLn $ "Failed to decode JSON in HTTP MCP: " ++ err
      respond $ W.responseLBS
        HTTP.status400
        [("Content-Type", "application/json")]
        (A.encode $ A.object
          [ "jsonrpc" A..= ("2.0" :: T.Text)
          , "error" A..= A.object
              [ "code" A..= (-32700)
              , "message" A..= ("Parse error" :: T.Text)
              , "data" A..= (A.String $ T.pack err)
              ]
          , "id" A..= A.Null
          ])
    Right (reqData :: MCPRequest) -> do
      putStrLn $ "Received HTTP MCP request: " ++ show reqData
      resp <- processMCPRequest reqData
      respond $ W.responseLBS
        HTTP.status200
        [("Content-Type", "application/json")]
        (A.encode resp)

wsApp :: ServerApp
wsApp pendingConn = do
  conn <- acceptRequest pendingConn
  putStrLn "New WebSocket connection"
  handleMessages conn

handleMessages :: Connection -> IO ()
handleMessages conn = forever $ do
  msg <- receiveDataMessage conn
  case msg of
    (Text bs) -> handleMessage conn bs
    (Binary bs) -> handleMessage conn bs

handleMessage :: Connection -> BL.ByteString -> IO ()
handleMessage conn bs = do
  case A.eitherDecode bs of
    Left err -> do
      putStrLn $ "Failed to decode JSON: " ++ err
      sendError conn (-32700) "Parse error" (A.object [])
    Right (req :: MCPRequest) -> do
      putStrLn $ "Received MCP request: " ++ show req
      response <- processMCPRequest req
      sendResponse conn response

-- MCP Protocol types
data MCPRequest = MCPRequest
  { mcpId :: Value
  , mcpMethod :: T.Text
  , mcpParams :: Maybe Value
  , mcpJsonrpc :: T.Text
  } deriving (Show)

instance A.FromJSON MCPRequest where
  parseJSON = A.withObject "MCPRequest" $ \o -> do
    mcpId <- o A..: "id"
    mcpMethod <- o A..: "method"
    mcpParams <- o A..:? "params"
    mcpJsonrpc <- o A..: "jsonrpc"
    pure MCPRequest{..}

data MCPResponse = MCPResponse
  { respId :: Value
  , respResult :: Maybe Value
  , respError :: Maybe MCPError
  , respJsonrpc :: T.Text
  } deriving (Show)

instance A.ToJSON MCPResponse where
  toJSON MCPResponse{..} = A.object
    [ "id" A..= respId
    , "result" A..= respResult
    , "error" A..= respError
    , "jsonrpc" A..= respJsonrpc
    ]

data MCPError = MCPError
  { errorCode :: Int
  , errorMessage :: T.Text
  , errorData :: Maybe Value
  } deriving (Show)

instance A.ToJSON MCPError where
  toJSON MCPError{..} = A.object
    [ "code" A..= errorCode
    , "message" A..= errorMessage
    , "data" A..= errorData
    ]

-- MCP Method handlers
processMCPRequest :: MCPRequest -> IO MCPResponse
processMCPRequest req = case mcpMethod req of
  "convert" -> handleConvertRequest req
  "version" -> handleVersionRequest req
  "list_methods" -> handleListMethodsRequest req
  _ -> pure $ MCPResponse
    { respId = mcpId req
    , respResult = Nothing
    , respError = Just $ MCPError
        { errorCode = -32601
        , errorMessage = "Method not found"
        , errorData = Nothing
        }
    , respJsonrpc = mcpJsonrpc req
    }

handleConvertRequest :: MCPRequest -> IO MCPResponse
handleConvertRequest req = case mcpParams req of
  Nothing -> pure $ MCPResponse
    { respId = mcpId req
    , respResult = Nothing
    , respError = Just $ MCPError
        { errorCode = -32602
        , errorMessage = "Invalid params"
        , errorData = Nothing
        }
    , respJsonrpc = mcpJsonrpc req
    }
  Just params -> do
    putStrLn $ "Converting with params: " ++ show params
    
    -- 解析params对象
    case A.fromJSON params of
      A.Error err -> pure $ MCPResponse
        { respId = mcpId req
        , respResult = Nothing
        , respError = Just $ MCPError
            { errorCode = -32600
            , errorMessage = "Invalid params format"
            , errorData = Just $ A.String $ T.pack err
            }
        , respJsonrpc = mcpJsonrpc req
        }
      A.Success (paramObj :: A.Object) -> do
        -- 尝试从params中提取必要的字段
        let mText = paramObj A..:? "text" :: A.Result (Maybe T.Text)
        let mFrom = paramObj A..:? "from" :: A.Result (Maybe T.Text)
        let mTo = paramObj A..:? "to" :: A.Result (Maybe T.Text)
        let mStandalone = paramObj A..:? "standalone" :: A.Result (Maybe Bool)
        
        case (mText, mFrom, mTo) of
          (A.Success (Just text), A.Success (Just fromFmt), A.Success (Just toFmt)) -> do
            putStrLn $ f"Converting from {fromFmt} to {toFmt}"
            let standalone = fromMaybe False mStandalone
            
            -- 创建Params结构
            let opts = defaultOpts {
                  optFrom = Just fromFmt,
                  optTo = Just toFmt,
                  optStandalone = standalone
                }
            let pandocParams = def {
                  options = opts,
                  text = text,
                  files = Nothing,
                  citeproc = Nothing
                }
            
            -- 调用pandoc-server的convertJSON函数
            let result = app (Wai.requestMethod, Wai.pathInfo) ???? -- 这里需要修复
            
            pure $ MCPResponse
              { respId = mcpId req
              , respResult = Just $ A.object [
                  ("status", A.String "success"),
                  ("output", A.String "NOT IMPLEMENTED YET - Placeholder")
                ]
              , respError = Nothing
              , respJsonrpc = mcpJsonrpc req
              }
          _ -> pure $ MCPResponse
            { respId = mcpId req
            , respResult = Nothing
            , respError = Just $ MCPError
                { errorCode = -32602
                , errorMessage = "Missing required params: text, from, to"
                , errorData = Nothing
                }
            , respJsonrpc = mcpJsonrpc req
            }

handleVersionRequest :: MCPRequest -> IO MCPResponse
handleVersionRequest req = do
  -- 暂时返回固定版本，实际实现应该调用pandoc库
  pure $ MCPResponse
    { respId = mcpId req
    , respResult = Just $ A.object [("version", A.String "3.9.0.2")]
    , respError = Nothing
    , respJsonrpc = mcpJsonrpc req
    }

handleListMethodsRequest :: MCPRequest -> IO MCPResponse
handleListMethodsRequest req = do
  let methods = ["convert", "version", "list_methods"]
  pure $ MCPResponse
    { respId = mcpId req
    , respResult = Just $ A.toJSON methods
    , respError = Nothing
    , respJsonrpc = mcpJsonrpc req
    }

-- Helper functions
sendError :: Connection -> Int -> T.Text -> Value -> IO ()
sendError conn code msg dataVal = sendTextData conn $ A.encode $ A.object
  [ "id" A..= A.Null
  , "error" A..= A.object
      [ "code" A..= code
      , "message" A..= msg
      , "data" A..= dataVal
      ]
  , "jsonrpc" A..= ("2.0" :: T.Text)
  ]

sendResponse :: Connection -> MCPResponse -> IO ()
sendResponse conn resp = sendTextData conn $ A.encode resp

-- 为了简单起见，我们直接使用pandoc库
-- 在实际中，我们可能会启动一个并行的HTTP服务器或重用现有的app

-- 启动服务器
