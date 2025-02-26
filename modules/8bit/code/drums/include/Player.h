#ifndef PLAYER_H
#define PLAYER_H

#include <SoftwareSerial.h>

#include <Arduino.h>
#define TOTAL_PLAYERS 8
#define MAX_VELOCITY 127

class Player {
  public:
    uint8_t sampleId = 0;
    const uint8_t* sampleData = 0;
    uint16_t sampleLenght = 0;
    uint8_t velocity = 100;
    uint16_t index = 0;
};

Player players[TOTAL_PLAYERS];

uint8_t getPlayHead() {
  int32_t combinedValue = 0;

  for (int lc=0; lc<TOTAL_PLAYERS; lc++) {
    Player* player = &players[lc];
    if (player->sampleData != 0) {
      if (player->index < player->sampleLenght) {
        combinedValue += (player->sampleData[player->index] - 127) * player->velocity;
        player->index += 1;
      } else {
        player->sampleData = 0;
      }
    }
  }

  return constrain((combinedValue / MAX_VELOCITY) + 127, 0, 255);
}

void startPlayer(uint8_t sampleId, const uint8_t* sampleData, uint16_t sampleLength, uint8_t velocity) {
  for (int lc=0; lc<TOTAL_PLAYERS; lc++) {
    if (players[lc].sampleData == 0) {
      players[lc].sampleId = sampleId;
      players[lc].sampleData = sampleData;
      players[lc].sampleLenght = sampleLength;
      players[lc].velocity = velocity;
      players[lc].index = 0;
      break;
    }
  }
}


#endif // PLAYER_H